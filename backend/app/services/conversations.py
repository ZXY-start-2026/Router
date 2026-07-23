from __future__ import annotations

from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.enums import GenerationStatus, TitleSource, UserMessageStatus
from app.core.errors import ConflictError, NotFoundError
from app.providers.model import ModelProvider
from app.repositories.chat import ChatRepository
from app.repositories.conversations import ConversationRepository
from app.schemas.chat import ModelOptionResponse
from app.schemas.common import CursorPage, decode_cursor, encode_cursor
from app.schemas.conversations import (
    ConversationListItem,
    ConversationResponse,
    CreateConversationRequest,
    UpdateConversationRequest,
)


class ConversationService:
    def __init__(
        self,
        session: Session,
        settings: Settings,
        model_provider: ModelProvider,
    ) -> None:
        self.session = session
        self.settings = settings
        self.provider = model_provider
        self.conversations = ConversationRepository(session)
        self.chat = ChatRepository(session)

    def create(self, request: CreateConversationRequest) -> ConversationResponse:
        title = request.title or "新会话"
        source = TitleSource.USER_EDIT if request.title else TitleSource.DEFAULT
        conversation = self.conversations.create_with_root_branch(title, source)
        self.session.commit()
        return self._to_response(conversation)

    def list_page(self, limit: int, cursor: str | None) -> CursorPage[ConversationListItem]:
        if not 1 <= limit <= self.settings.conversation_page_max_size:
            raise ConflictError("分页数量超出允许范围")
        cursor_key = decode_cursor(cursor) if cursor else None
        rows = self.conversations.list_page(limit, cursor_key)
        has_more = len(rows) > limit
        page_rows = rows[:limit]
        items = [self._to_list_item(row) for row in page_rows]
        next_cursor = None
        if has_more and page_rows:
            last = page_rows[-1]
            next_cursor = encode_cursor(last.updated_at, last.id)
        return CursorPage(items=items, next_cursor=next_cursor, has_more=has_more)

    def get(self, conversation_id: str) -> ConversationResponse:
        conversation = self._require_conversation(conversation_id)
        return self._to_response(conversation)

    def rename(
        self, conversation_id: str, request: UpdateConversationRequest
    ) -> ConversationResponse:
        conversation = self._require_conversation(conversation_id)
        self.conversations.update_title(
            conversation, request.title, TitleSource.USER_EDIT
        )
        self.session.commit()
        return self._to_response(conversation)

    def list_model_options(self) -> list[ModelOptionResponse]:
        return [
            ModelOptionResponse(
                model_key=option.model_key,
                label=option.label,
                available=option.available,
            )
            for option in self.provider.model_options()
        ]

    def _require_conversation(self, conversation_id: str):
        conversation = self.conversations.get(conversation_id)
        if conversation is None:
            raise NotFoundError("会话不存在")
        if conversation.active_branch_id is None:
            raise ConflictError("会话缺少活动分支")
        return conversation

    def _to_response(self, conversation) -> ConversationResponse:
        latest = self.chat.latest_turn(conversation.active_branch_id)
        return ConversationResponse(
            id=conversation.id,
            title=conversation.title,
            title_source=conversation.title_source,
            active_branch_id=conversation.active_branch_id,
            created_at=conversation.created_at,
            updated_at=conversation.updated_at,
            generation_status=self._generation_status(latest),
        )

    def _to_list_item(self, conversation) -> ConversationListItem:
        latest = self.chat.latest_turn(conversation.active_branch_id)
        preview = None
        if latest:
            preview = " ".join(latest.user_message.content.split())[:100]
        return ConversationListItem(
            id=conversation.id,
            title=conversation.title,
            latest_message_preview=preview,
            updated_at=conversation.updated_at,
            generation_status=self._generation_status(latest),
        )

    @staticmethod
    def _generation_status(latest) -> GenerationStatus:
        if latest is None:
            return GenerationStatus.IDLE
        if latest.active_answer is not None:
            return GenerationStatus.SUCCEEDED
        mapping = {
            UserMessageStatus.PENDING: GenerationStatus.GENERATING,
            UserMessageStatus.HAS_ACTIVE_ANSWER: GenerationStatus.FAILED,
            UserMessageStatus.GENERATION_FAILED: GenerationStatus.FAILED,
        }
        return mapping[latest.user_message.status]
