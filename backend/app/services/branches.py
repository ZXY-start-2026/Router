from __future__ import annotations

from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.enums import (
    BranchPointType,
    BranchStatus,
    GenerationMode,
    GenerationStatus,
)
from app.core.errors import ConflictError, NotFoundError
from app.db.models_core import AssistantAnswerVersion, Branch, BranchMessage, Conversation
from app.providers.registry import ProviderRegistry
from app.repositories.chat import ChatRepository
from app.repositories.conversations import ConversationRepository
from app.schemas.branches import (
    BranchActivationResponse,
    BranchListResponse,
    BranchResponse,
    EditMessageRequest,
    GenerationOperationResponse,
)
from app.schemas.chat import GenerationResultSummary
from app.services.chat import ChatService
from app.services.generation import GenerationService


class BranchService:
    def __init__(
        self, session: Session, settings: Settings, providers: ProviderRegistry
    ) -> None:
        self.session = session
        self.settings = settings
        self.providers = providers
        self.chat = ChatRepository(session)
        self.conversations = ConversationRepository(session)

    def edit_user_message(
        self, message_id: str, request: EditMessageRequest
    ) -> GenerationOperationResponse:
        conversation, source_branch = self._require_active_branch(request.branch_id)
        source_link = self.chat.get_branch_message(source_branch.id, message_id)
        if source_link is None:
            raise NotFoundError("消息不在指定分支中")

        branch = Branch(
            conversation_id=conversation.id,
            parent_branch_id=source_branch.id,
            branch_point_type=BranchPointType.USER_MESSAGE_EDIT,
            branch_point_message_id=message_id,
            status=BranchStatus.ACTIVE,
        )
        self.session.add(branch)
        self.session.flush()
        self.chat.copy_links(
            source_branch.id, branch.id, source_link.logical_position - 1
        )
        message, link = self.chat.append_user_message(
            branch,
            request.content,
            logical_position=source_link.logical_position,
        )
        branch.complete_turn_count = self.chat.count_complete_turns(branch.id)
        self.conversations.set_active_branch(conversation, branch)
        self.session.commit()

        generator = self._generator()
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
        return GenerationOperationResponse(
            conversation_id=conversation.id,
            branch_id=branch.id,
            created_branch_id=branch.id,
            user_message=ChatService.user_response(message, link),
            active_answer=(
                ChatService.answer_response(
                    run.answer, finish_reason=run.finish_reason
                )
                if run.status == GenerationStatus.SUCCEEDED
                else None
            ),
            generation=self._generation_summary(run),
        )

    def fork_for_answer(
        self,
        conversation: Conversation,
        source_branch: Branch,
        source_link: BranchMessage,
        answer: AssistantAnswerVersion,
    ) -> Branch:
        branch = Branch(
            conversation_id=conversation.id,
            parent_branch_id=source_branch.id,
            branch_point_type=BranchPointType.ANSWER_VERSION_ACTIVATE,
            branch_point_message_id=source_link.user_message_id,
            branch_point_answer_version_id=answer.id,
            status=BranchStatus.ACTIVE,
        )
        self.session.add(branch)
        self.session.flush()
        self.chat.copy_links(
            source_branch.id, branch.id, source_link.logical_position
        )
        target_link = self.chat.get_branch_message(
            branch.id, source_link.user_message_id
        )
        message = self.chat.get_message(source_link.user_message_id)
        if target_link is None or message is None:
            raise ConflictError("新分支缺少分叉消息")
        self.chat.activate_answer(branch, target_link, message, answer)
        self.conversations.set_active_branch(conversation, branch)
        return branch

    def list(self, conversation_id: str) -> BranchListResponse:
        conversation = self.conversations.get(conversation_id)
        if conversation is None or conversation.active_branch_id is None:
            raise NotFoundError("会话不存在")
        branches = self.conversations.list_branches(conversation_id)
        return BranchListResponse(
            conversation_id=conversation.id,
            active_branch_id=conversation.active_branch_id,
            items=[
                self._branch_response(item, conversation.active_branch_id)
                for item in branches
            ],
        )

    def activate(
        self, conversation_id: str, branch_id: str
    ) -> BranchActivationResponse:
        conversation = self.conversations.get(conversation_id)
        branch = self.conversations.get_branch(branch_id)
        if conversation is None:
            raise NotFoundError("会话不存在")
        if (
            branch is None
            or branch.conversation_id != conversation.id
            or branch.status != BranchStatus.ACTIVE
        ):
            raise ConflictError("分支不属于指定会话或不可用")
        self.conversations.set_active_branch(conversation, branch)
        self.session.commit()
        return BranchActivationResponse(
            conversation_id=conversation.id,
            active_branch_id=branch.id,
        )

    def _require_active_branch(
        self, branch_id: str
    ) -> tuple[Conversation, Branch]:
        branch = self.conversations.get_branch(branch_id)
        if branch is None:
            raise NotFoundError("分支不存在")
        conversation = self.conversations.get(branch.conversation_id)
        if conversation is None:
            raise NotFoundError("会话不存在")
        if conversation.active_branch_id != branch.id:
            raise ConflictError("只能操作当前活动分支")
        return conversation, branch

    def _generator(self) -> GenerationService:
        return GenerationService(
            self.session,
            self.settings,
            self.providers.models,
            self.providers.model,
            self.providers,
        )

    @staticmethod
    def _branch_response(branch: Branch, active_id: str) -> BranchResponse:
        return BranchResponse(
            id=branch.id,
            parent_branch_id=branch.parent_branch_id,
            branch_point_type=branch.branch_point_type,
            branch_point_message_id=branch.branch_point_message_id,
            branch_point_answer_version_id=branch.branch_point_answer_version_id,
            complete_turn_count=branch.complete_turn_count,
            created_at=branch.created_at,
            is_active=branch.id == active_id,
        )

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
