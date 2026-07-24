from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.models_core import new_id, utc_now
from app.db.session import Base


class RoleTemplate(Base):
    __tablename__ = "role_templates"
    __table_args__ = (Index("ix_role_templates_created", "created_at", "id"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    persona: Mapped[str] = mapped_column(Text, nullable=False, default="")
    background: Mapped[str] = mapped_column(Text, nullable=False, default="")
    domain: Mapped[str] = mapped_column(Text, nullable=False, default="")
    traits_json: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    style: Mapped[str] = mapped_column(Text, nullable=False, default="")
    constraints_text: Mapped[str] = mapped_column(Text, nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )


class RoleVersion(Base):
    __tablename__ = "role_versions"
    __table_args__ = (
        UniqueConstraint("conversation_id", "version_number", name="uq_role_conversation_version"),
        Index("ix_role_versions_conversation", "conversation_id", "version_number"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    conversation_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("conversations.id"), nullable=False
    )
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    source_template_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("role_templates.id"), nullable=True
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    persona: Mapped[str] = mapped_column(Text, nullable=False, default="")
    background: Mapped[str] = mapped_column(Text, nullable=False, default="")
    domain: Mapped[str] = mapped_column(Text, nullable=False, default="")
    traits_json: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    style: Mapped[str] = mapped_column(Text, nullable=False, default="")
    constraints_text: Mapped[str] = mapped_column(Text, nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )
