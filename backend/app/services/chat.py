from __future__ import annotations

from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.enums import ErrorCategory, GenerationStatus, SearchStatus, SelectionMode, TitleSource
from app.core.errors import AppError, ConflictError, NotFoundError, ProviderError
from app.db.models_core import AssistantAnswerVersion, BranchMessage, UserMessage
from app.providers.registry import ProviderRegistry
from app.providers.search import SearchRequest, SearchResponse
from app.repositories.chat import ChatRepository, EffectiveTurn
from app.repositories.conversations import ConversationRepository
from app.repositories.generation import GenerationRepository
from app.schemas.chat import (
    AnswerResponse,
    BranchMessagesResponse,
    BranchTurnResponse,
    GenerationResultSummary,
    SendMessageRequest,
    SendMessageResponse,
    UserMessageResponse,
)
from app.schemas.generation import (
    GenerationAttemptResponse,
    GenerationTaskResponse,
    RouteCandidateResponse,
    SearchSnapshotResponse,
)
from app.services.context import ContextService
from app.services.generation import GenerationOutcome, GenerationService
from app.services.routing import RoutingService
from app.services.title import make_title


class ChatService:
    def __init__(
        self, session: Session, settings: Settings, providers: ProviderRegistry
    ) -> None:
        self.session = session
        self.settings = settings
        self.providers = providers
        self.conversations = ConversationRepository(session)
        self.chat = ChatRepository(session)
        self.generation = GenerationRepository(session)

    def list_active_branch_messages(self, conversation_id: str) -> BranchMessagesResponse:
        conversation, branch = self._require_active_branch(conversation_id)
        turns = self.chat.list_effective_messages(branch.id)
        return BranchMessagesResponse(
            conversation_id=conversation.id,
            branch_id=branch.id,
            items=[self._turn_response(turn) for turn in turns],
        )

    def send_message(
        self, conversation_id: str, request: SendMessageRequest
    ) -> SendMessageResponse:
        conversation, branch = self._require_active_branch(conversation_id)
        message, link = self.chat.append_user_message(branch, request.content)
        answer = self.chat.create_answer_version(message.id, request.selection_mode)
        if conversation.title_source == TitleSource.DEFAULT:
            self.conversations.update_title(
                conversation,
                make_title(request.content, self.settings.title_max_chars),
                TitleSource.AUTO_FIRST_MESSAGE,
            )
        else:
            self.conversations.touch(conversation)
        self.session.commit()

        search_response = self._search(request.content)
        search_snapshot = self.generation.create_search_snapshot(message, search_response)
        prepared = ContextService(self.session, self.settings).prepare(
            branch_id=branch.id,
            message=message,
            search_snapshot=search_snapshot,
            search_response=search_response,
        )
        task = self.generation.create_task(
            user_message_id=message.id,
            branch_id=branch.id,
            selection_mode=request.selection_mode,
            requested_model_key=request.model_key,
            search_snapshot_id=search_snapshot.id,
            context_snapshot_id=prepared.snapshot.id,
        )
        self.generation.bind_answer_to_task(answer, task)
        self.session.commit()

        route_plan = None
        try:
            generator = GenerationService(
                self.session,
                self.settings,
                self.providers.models,
                self.providers.model,
            )
            if request.selection_mode == SelectionMode.AUTO_ROUTE:
                route_plan = RoutingService(
                    self.session,
                    self.settings,
                    self.providers.models,
                    self.providers.router,
                    self.providers.tokenizer,
                ).route(task, request.content, prepared.prompt)
                answer.route_snapshot_id = route_plan.snapshot.id
                self.session.commit()
                outcome = generator.execute_auto(
                    task, route_plan, prepared.prompt, request.content
                )
            else:
                assert request.model_key is not None
                outcome = generator.execute_manual(
                    task, request.model_key, prepared.prompt, request.content
                )
        except AppError as error:
            category = error.category if isinstance(error, ProviderError) else ErrorCategory.UNKNOWN
            return self._record_failure(
                conversation,
                message,
                answer,
                link,
                task,
                search_response.status,
                category,
                error.code,
                error.message,
            )
        except Exception:
            return self._record_failure(
                conversation,
                message,
                answer,
                link,
                task,
                search_response.status,
                ErrorCategory.UNKNOWN,
                "GENERATION_PIPELINE_ERROR",
                "生成流程失败",
            )

        if outcome.result is None or outcome.model is None:
            error = outcome.failure or ProviderError("所有候选模型均生成失败")
            return self._record_failure(
                conversation,
                message,
                answer,
                link,
                task,
                search_response.status,
                error.category,
                error.provider_code or error.code,
                error.message,
            )

        candidate = (
            self.generation.get_candidate(route_plan.snapshot.id, outcome.model.model_key)
            if route_plan is not None
            else None
        )
        actual_cost = GenerationService.actual_cost(
            outcome.model,
            outcome.result.input_tokens,
            outcome.result.output_tokens,
        )
        self.chat.finalize_answer(
            branch,
            link,
            message,
            answer,
            content=outcome.result.content,
            model_key=outcome.result.model_key,
            model_id=outcome.result.model_id,
            display_name=outcome.model.display_name,
            selection_mode=outcome.selection_mode,
            route_snapshot_id=route_plan.snapshot.id if route_plan else None,
            predicted_input_tokens=(candidate.predicted_input_tokens if candidate else None),
            predicted_output_tokens=(candidate.predicted_output_tokens if candidate else None),
            predicted_cost=(candidate.predicted_cost if candidate else None),
            actual_input_tokens=outcome.result.input_tokens,
            actual_output_tokens=outcome.result.output_tokens,
            actual_cost=actual_cost,
            price_version=self.settings.price_version,
        )
        self.generation.succeed_task(task)
        self.conversations.touch(conversation)
        self.session.commit()
        return SendMessageResponse(
            user_message=self._user_response(message, link),
            active_answer=self._answer_response(answer),
            generation=GenerationResultSummary(
                status=GenerationStatus.SUCCEEDED,
                task_id=task.id,
                search_status=search_response.status.value,
                selected_model_key=outcome.result.model_key,
                route_snapshot_id=task.route_snapshot_id,
            ),
        )

    def get_generation_task(self, task_id: str) -> GenerationTaskResponse:
        details = self.generation.get_details(task_id)
        if details is None:
            raise NotFoundError("生成任务不存在")
        return GenerationTaskResponse(
            id=details.task.id,
            status=details.task.status,
            requested_model_key=details.task.requested_model_key,
            failure_category=details.task.failure_category,
            failure_message=details.task.failure_message,
            created_at=details.task.created_at,
            completed_at=details.task.completed_at,
            search=SearchSnapshotResponse(
                provider=details.search.provider,
                status=details.search.status,
                failure_code=details.search.failure_code,
                failure_message=details.search.failure_message,
                latency_ms=details.search.latency_ms,
            ),
            route_snapshot_id=details.route.id if details.route else None,
            candidates=[
                RouteCandidateResponse(
                    model_key=item.model_key,
                    display_name=item.display_name_snapshot,
                    eligible=item.eligible,
                    ineligible_reason=item.ineligible_reason,
                    predicted_accuracy=item.predicted_accuracy,
                    predicted_input_tokens=item.predicted_input_tokens,
                    predicted_output_tokens=item.predicted_output_tokens,
                    predicted_cost=item.predicted_cost,
                    cost_score=item.cost_score,
                    route_score=item.route_score,
                    rank=item.rank,
                )
                for item in details.candidates
            ],
            attempts=[
                GenerationAttemptResponse(
                    attempt_index=item.attempt_index,
                    model_key=item.model_key,
                    display_name=item.display_name_snapshot,
                    response_model=item.response_model_snapshot,
                    started_at=item.started_at,
                    ended_at=item.ended_at,
                    status=item.status,
                    finish_reason=item.finish_reason,
                    error_category=item.error_category,
                    error_code=item.error_code,
                    error_message=item.error_message,
                    retry_of_attempt_id=item.retry_of_attempt_id,
                    actual_input_tokens=item.actual_input_tokens,
                    actual_output_tokens=item.actual_output_tokens,
                    charged_cost=item.charged_cost,
                    price_version=item.price_version,
                )
                for item in details.attempts
            ],
        )

    def _search(self, query: str) -> SearchResponse:
        try:
            return self.providers.search.search(
                SearchRequest(query=query, max_results=self.settings.search_max_results)
            )
        except Exception:
            return SearchResponse(
                provider="360",
                status=SearchStatus.FAILED,
                query=query,
                failure_code="SEARCH_PROVIDER_ERROR",
                failure_message="联网搜索失败，本轮继续使用模型自身知识回答。",
            )

    def _record_failure(
        self,
        conversation,
        message: UserMessage,
        answer: AssistantAnswerVersion,
        link: BranchMessage,
        task,
        search_status: SearchStatus,
        category: ErrorCategory,
        code: str,
        message_text: str,
    ) -> SendMessageResponse:
        self.generation.fail_task(task, category, message_text)
        self.chat.mark_answer_failed(message, answer)
        self.conversations.touch(conversation)
        self.session.commit()
        return SendMessageResponse(
            user_message=self._user_response(message, link),
            active_answer=None,
            generation=GenerationResultSummary(
                status=GenerationStatus.FAILED,
                task_id=task.id,
                search_status=search_status.value,
                route_snapshot_id=task.route_snapshot_id,
                failure_code=code,
                failure_message=message_text,
            ),
        )

    def _require_active_branch(self, conversation_id: str):
        conversation = self.conversations.get(conversation_id)
        if conversation is None:
            raise NotFoundError("会话不存在")
        branch = self.conversations.get_active_branch(conversation)
        if branch is None:
            raise ConflictError("会话缺少活动分支")
        return conversation, branch

    def _turn_response(self, turn: EffectiveTurn) -> BranchTurnResponse:
        return BranchTurnResponse(
            user_message=self._user_response(turn.user_message, turn.branch_message),
            active_answer=(
                self._answer_response(turn.active_answer)
                if turn.active_answer is not None
                else None
            ),
        )

    @staticmethod
    def _user_response(message: UserMessage, link: BranchMessage) -> UserMessageResponse:
        return UserMessageResponse(
            id=message.id,
            content=message.content,
            status=message.status,
            logical_position=link.logical_position,
            created_at=message.created_at,
        )

    @staticmethod
    def _answer_response(answer: AssistantAnswerVersion) -> AnswerResponse:
        if answer.content is None or answer.model_key is None or answer.model_id_snapshot is None or answer.completed_at is None:
            raise ConflictError("生效回答数据不完整")
        return AnswerResponse(
            id=answer.id,
            content=answer.content,
            model_key=answer.model_key,
            model_id=answer.model_id_snapshot,
            display_name=answer.display_name_snapshot or answer.model_key,
            selection_mode=answer.selection_mode,
            status=answer.status,
            created_at=answer.created_at,
            completed_at=answer.completed_at,
            predicted_input_tokens=answer.predicted_input_tokens,
            predicted_output_tokens=answer.predicted_output_tokens,
            actual_input_tokens=answer.actual_input_tokens,
            actual_output_tokens=answer.actual_output_tokens,
            predicted_cost=answer.predicted_cost,
            actual_cost=answer.actual_cost,
            price_version=answer.price_version,
        )
