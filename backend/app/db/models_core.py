from __future__ import annotations

import uuid
from datetime import datetime, timezone

from decimal import Decimal

from sqlalchemy import DateTime, Enum, ForeignKey, Index, Integer, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.enums import (
    AnswerVersionStatus,
    BranchPointType,
    BranchStatus,
    SelectionMode,
    TitleSource,
    UserMessageStatus,
)
from app.db.session import Base


def new_id() -> str:
    return str(uuid.uuid4())


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class Conversation(Base):
    __tablename__ = "conversations"
    __table_args__ = (Index("ix_conversations_updated_id", "updated_at", "id"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    title_source: Mapped[TitleSource] = mapped_column(Enum(TitleSource), nullable=False)
    active_branch_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("branches.id"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )


class Branch(Base):
    __tablename__ = "branches"
    __table_args__ = (Index("ix_branches_conversation_created", "conversation_id", "created_at"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    conversation_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("conversations.id"), nullable=False
    )
    parent_branch_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("branches.id"), nullable=True
    )
    branch_point_type: Mapped[BranchPointType] = mapped_column(
        Enum(BranchPointType), nullable=False, default=BranchPointType.ROOT
    )
    branch_point_message_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    branch_point_answer_version_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    complete_turn_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    status: Mapped[BranchStatus] = mapped_column(
        Enum(BranchStatus), nullable=False, default=BranchStatus.ACTIVE
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )


class UserMessage(Base):
    __tablename__ = "user_messages"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    search_snapshot_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    status: Mapped[UserMessageStatus] = mapped_column(
        Enum(UserMessageStatus), nullable=False, default=UserMessageStatus.PENDING
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )


class AssistantAnswerVersion(Base):
    __tablename__ = "assistant_answer_versions"
    __table_args__ = (Index("ix_answers_message_created", "user_message_id", "created_at"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    user_message_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("user_messages.id"), nullable=False
    )
    model_key: Mapped[str | None] = mapped_column(String(32), nullable=True)
    display_name_snapshot: Mapped[str | None] = mapped_column(String(200), nullable=True)
    model_id_snapshot: Mapped[str | None] = mapped_column(String(200), nullable=True)
    generation_task_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("generation_tasks.id"), nullable=True, unique=True
    )
    route_snapshot_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("route_snapshots.id"), nullable=True
    )
    selection_mode: Mapped[SelectionMode] = mapped_column(Enum(SelectionMode), nullable=False)
    status: Mapped[AnswerVersionStatus] = mapped_column(
        Enum(AnswerVersionStatus), nullable=False, default=AnswerVersionStatus.GENERATING
    )
    content: Mapped[str | None] = mapped_column(Text, nullable=True)
    predicted_input_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    predicted_output_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    actual_input_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    actual_output_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    predicted_cost: Mapped[Decimal | None] = mapped_column(Numeric(20, 10), nullable=True)
    actual_cost: Mapped[Decimal | None] = mapped_column(Numeric(20, 10), nullable=True)
    input_token_error: Mapped[int | None] = mapped_column(Integer, nullable=True)
    output_token_error: Mapped[int | None] = mapped_column(Integer, nullable=True)
    cost_error: Mapped[Decimal | None] = mapped_column(Numeric(20, 10), nullable=True)
    price_version: Mapped[str | None] = mapped_column(String(100), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class BranchMessage(Base):
    __tablename__ = "branch_messages"
    __table_args__ = (
        UniqueConstraint("branch_id", "logical_position", name="uq_branch_message_position"),
        UniqueConstraint("branch_id", "user_message_id", name="uq_branch_user_message"),
        Index("ix_branch_messages_order", "branch_id", "logical_position"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    branch_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("branches.id"), nullable=False
    )
    user_message_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("user_messages.id"), nullable=False
    )
    logical_position: Mapped[int] = mapped_column(Integer, nullable=False)
    active_answer_version_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("assistant_answer_versions.id"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )
