from __future__ import annotations

from datetime import datetime

from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session

from app.core.enums import BranchPointType, BranchStatus, TitleSource
from app.db.models_core import Branch, Conversation, utc_now


class ConversationRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def create_with_root_branch(
        self, title: str, title_source: TitleSource
    ) -> Conversation:
        now = utc_now()
        conversation = Conversation(
            title=title,
            title_source=title_source,
            created_at=now,
            updated_at=now,
        )
        self.session.add(conversation)
        self.session.flush()
        branch = Branch(
            conversation_id=conversation.id,
            branch_point_type=BranchPointType.ROOT,
            status=BranchStatus.ACTIVE,
            created_at=now,
        )
        self.session.add(branch)
        self.session.flush()
        conversation.active_branch_id = branch.id
        return conversation

    def get(self, conversation_id: str) -> Conversation | None:
        return self.session.get(Conversation, conversation_id)

    def get_active_branch(self, conversation: Conversation) -> Branch | None:
        if conversation.active_branch_id is None:
            return None
        return self.session.get(Branch, conversation.active_branch_id)

    def get_branch(self, branch_id: str) -> Branch | None:
        return self.session.get(Branch, branch_id)

    def list_branches(self, conversation_id: str) -> list[Branch]:
        return list(
            self.session.scalars(
                select(Branch)
                .where(
                    Branch.conversation_id == conversation_id,
                    Branch.status == BranchStatus.ACTIVE,
                )
                .order_by(Branch.created_at.asc(), Branch.id.asc())
            )
        )

    def set_active_branch(
        self, conversation: Conversation, branch: Branch
    ) -> Conversation:
        conversation.active_branch_id = branch.id
        self.touch(conversation)
        return conversation

    def list_page(
        self,
        limit: int,
        cursor_key: tuple[datetime, str] | None,
    ) -> list[Conversation]:
        statement = select(Conversation)
        if cursor_key is not None:
            updated_at, item_id = cursor_key
            statement = statement.where(
                or_(
                    Conversation.updated_at < updated_at,
                    and_(
                        Conversation.updated_at == updated_at,
                        Conversation.id < item_id,
                    ),
                )
            )
        statement = statement.order_by(
            Conversation.updated_at.desc(), Conversation.id.desc()
        ).limit(limit + 1)
        return list(self.session.scalars(statement))

    def update_title(
        self, conversation: Conversation, title: str, source: TitleSource
    ) -> Conversation:
        conversation.title = title
        conversation.title_source = source
        self.touch(conversation)
        return conversation

    @staticmethod
    def touch(conversation: Conversation, at: datetime | None = None) -> None:
        conversation.updated_at = at or utc_now()

