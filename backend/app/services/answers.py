from __future__ import annotations

from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.enums import (
    AnswerVersionStatus,
    GenerationMode,
    GenerationStatus,
    RegenerationMode,
    SelectionMode,
)
from app.core.errors import ConflictError, NotFoundError
from app.db.models_core import Branch, BranchMessage, Conversation
from app.providers.registry import ProviderRegistry
from app.repositories.chat import ChatRepository
from app.repositories.conversations import ConversationRepository
from app.repositories.generation import GenerationRepository
from app.schemas.branches import (
    ActivateAnswerRequest,
    AnswerActivationResponse,
    AnswerVersionsResponse,
    GenerationOperationResponse,
    RegenerateRequest,
)
from app.schemas.chat import GenerationResultSummary
from app.services.branches import BranchService
from app.services.chat import ChatService
from app.services.generation import GenerationService


class AnswerService:
    def __init__(
        self, session: Session, settings: Settings, providers: ProviderRegistry
    ) -> None:
        self.session = session
        self.settings = settings
        self.providers = providers
        self.chat = ChatRepository(session)
        self.conversations = ConversationRepository(session)
        self.generation = GenerationRepository(session)
        self.branches = BranchService(session, settings, providers)

    def list_versions(
        self, message_id: str, branch_id: str
    ) -> AnswerVersionsResponse:
        branch = self.conversations.get_branch(branch_id)
        link = self.chat.get_branch_message(branch_id, message_id)
        if branch is None or link is None:
            raise NotFoundError("消息不在指定分支中")
        items = self.chat.list_successful_answers(message_id)
        return AnswerVersionsResponse(
            user_message_id=message_id,
            branch_id=branch_id,
            active_answer_version_id=link.active_answer_version_id,
            items=[
                ChatService.answer_response(
                    item.answer, finish_reason=item.finish_reason
                )
                for item in items
            ],
        )

    def regenerate(
        self, message_id: str, request: RegenerateRequest
    ) -> GenerationOperationResponse:
        conversation, branch, link = self._require_active_message(
            request.branch_id, message_id
        )
        message = self.chat.get_message(message_id)
        if message is None:
            raise NotFoundError("消息不存在")
        if message.search_snapshot_id is None:
            raise ConflictError("原消息没有可复用的搜索快照")
        search_snapshot = self.generation.get_search_snapshot(
            message.search_snapshot_id
        )
        if search_snapshot is None:
            raise ConflictError("原消息搜索快照不存在")

        source_answer = (
            self.chat.get_answer(link.active_answer_version_id)
            if link.active_answer_version_id
            else None
        )
        if request.mode == RegenerationMode.REGENERATE_ORIGINAL_MODEL:
            if source_answer is None or source_answer.model_key is None:
                raise ConflictError("当前消息没有可复用原模型的成功回答")
            selection_mode = SelectionMode.USER_SELECTED
            requested_model_key = source_answer.model_key
        elif request.mode == RegenerationMode.REGENERATE_AUTO_ROUTE:
            selection_mode = SelectionMode.AUTO_ROUTE
            requested_model_key = None
        else:
            selection_mode = SelectionMode.USER_SELECTED
            requested_model_key = request.model_key

        run = self._generator().run(
            branch=branch,
            message=message,
            search_snapshot=search_snapshot,
            selection_mode=selection_mode,
            requested_model_key=requested_model_key,
            generation_mode=GenerationMode.REGENERATE,
            source_answer_version_id=source_answer.id if source_answer else None,
        )
        created_branch_id = None
        result_branch = branch
        if run.status == GenerationStatus.SUCCEEDED:
            result_branch, created_branch_id = self._activate_with_branch_safety(
                conversation, branch, link, run.answer
            )
        self.conversations.touch(conversation)
        self.session.commit()
        active = (
            run.answer
            if run.status == GenerationStatus.SUCCEEDED
            else source_answer
        )
        return GenerationOperationResponse(
            conversation_id=conversation.id,
            branch_id=result_branch.id,
            created_branch_id=created_branch_id,
            user_message=ChatService.user_response(message, link),
            active_answer=(
                ChatService.answer_response(
                    active,
                    finish_reason=(
                        run.finish_reason
                        if active is run.answer
                        else self._finish_reason(active.id)
                    ),
                )
                if active is not None
                else None
            ),
            generation=self._generation_summary(run),
        )

    def activate(
        self,
        message_id: str,
        answer_id: str,
        request: ActivateAnswerRequest,
    ) -> AnswerActivationResponse:
        conversation, branch, link = self._require_active_message(
            request.branch_id, message_id
        )
        answer = self.chat.get_answer(answer_id)
        if answer is None:
            raise NotFoundError("回答版本不存在")
        if answer.user_message_id != message_id:
            raise ConflictError("回答版本不属于目标消息")
        if answer.status not in {
            AnswerVersionStatus.SUCCEEDED_ACTIVE,
            AnswerVersionStatus.SUCCEEDED_INACTIVE,
        }:
            raise ConflictError("只有成功回答可以设为当前版本")
        created_branch_id = None
        result_branch = branch
        if link.active_answer_version_id != answer.id:
            result_branch, created_branch_id = self._activate_with_branch_safety(
                conversation, branch, link, answer
            )
            self.conversations.touch(conversation)
            self.session.commit()
        return AnswerActivationResponse(
            conversation_id=conversation.id,
            branch_id=result_branch.id,
            created_branch_id=created_branch_id,
            active_answer=ChatService.answer_response(
                answer, finish_reason=self._finish_reason(answer.id)
            ),
        )

    def _activate_with_branch_safety(
        self,
        conversation: Conversation,
        branch: Branch,
        link: BranchMessage,
        answer,
    ) -> tuple[Branch, str | None]:
        if self.chat.has_later_messages(branch.id, link.logical_position):
            created = self.branches.fork_for_answer(
                conversation, branch, link, answer
            )
            return created, created.id
        message = self.chat.get_message(link.user_message_id)
        if message is None:
            raise NotFoundError("消息不存在")
        self.chat.activate_answer(branch, link, message, answer)
        return branch, None

    def _require_active_message(
        self, branch_id: str, message_id: str
    ) -> tuple[Conversation, Branch, BranchMessage]:
        branch = self.conversations.get_branch(branch_id)
        if branch is None:
            raise NotFoundError("分支不存在")
        conversation = self.conversations.get(branch.conversation_id)
        if conversation is None:
            raise NotFoundError("会话不存在")
        if conversation.active_branch_id != branch.id:
            raise ConflictError("只能操作当前活动分支")
        link = self.chat.get_branch_message(branch.id, message_id)
        if link is None:
            raise NotFoundError("消息不在指定分支中")
        return conversation, branch, link

    def _generator(self) -> GenerationService:
        return GenerationService(
            self.session,
            self.settings,
            self.providers.models,
            self.providers.model,
            self.providers,
        )

    def _finish_reason(self, answer_id: str) -> str | None:
        for item in self.chat.list_successful_answers(
            self.chat.get_answer(answer_id).user_message_id
        ):
            if item.answer.id == answer_id:
                return item.finish_reason
        return None

    @staticmethod
    def _generation_summary(run) -> GenerationResultSummary:
        return GenerationResultSummary(
            status=run.status,
            task_id=run.task.id if run.task else None,
            search_status=run.search_status.value,
            selected_model_key=run.selected_model_key,
            route_snapshot_id=run.task.route_snapshot_id if run.task else None,
            failure_code=run.failure_code,
            failure_message=run.failure_message,
        )
