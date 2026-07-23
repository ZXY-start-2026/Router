from __future__ import annotations

from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.enums import GenerationMode, GenerationStatus, SelectionMode, TitleSource
from app.core.errors import ConflictError, NotFoundError
from app.db.models_core import AssistantAnswerVersion, BranchMessage, UserMessage
from app.providers.registry import ProviderRegistry
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
from app.services.generation import GenerationService
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
        if conversation.title_source == TitleSource.DEFAULT:
            self.conversations.update_title(
                conversation,
                make_title(request.content, self.settings.title_max_chars),
                TitleSource.AUTO_FIRST_MESSAGE,
            )
        else:
            self.conversations.touch(conversation)
        self.session.commit()

        generator = GenerationService(
            self.session,
            self.settings,
            self.providers.models,
            self.providers.model,
            self.providers,
        )
        search_snapshot = generator.create_search_snapshot(message)
        run = generator.run(
            branch=branch,
            message=message,
            search_snapshot=search_snapshot,
            selection_mode=request.selection_mode,
            requested_model_key=request.model_key,
            generation_mode=GenerationMode.NEW_MESSAGE,
        )
        if run.status == GenerationStatus.SUCCEEDED:
            self.chat.activate_answer(branch, link, message, run.answer)
        self.conversations.touch(conversation)
        self.session.commit()
        return SendMessageResponse(
            user_message=self.user_response(message, link),
            active_answer=(
                self.answer_response(run.answer, finish_reason=run.finish_reason)
                if run.status == GenerationStatus.SUCCEEDED
                else None
            ),
            generation=GenerationResultSummary(
                status=run.status,
                task_id=run.task.id if run.task else None,
                search_status=run.search_status.value,
                selected_model_key=run.selected_model_key,
                route_snapshot_id=run.task.route_snapshot_id if run.task else None,
                failure_code=run.failure_code,
                failure_message=run.failure_message,
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
            user_message=self.user_response(turn.user_message, turn.branch_message),
            active_answer=(
                self.answer_response(
                    turn.active_answer, finish_reason=turn.finish_reason
                )
                if turn.active_answer is not None
                else None
            ),
        )

    @staticmethod
    def user_response(message: UserMessage, link: BranchMessage) -> UserMessageResponse:
        return UserMessageResponse(
            id=message.id,
            content=message.content,
            status=message.status,
            logical_position=link.logical_position,
            created_at=message.created_at,
        )

    @staticmethod
    def answer_response(
        answer: AssistantAnswerVersion, finish_reason: str | None = None
    ) -> AnswerResponse:
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
            finish_reason=finish_reason,
        )
