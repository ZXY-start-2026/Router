from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, DateTime, Enum, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.enums import MemoryUpdateStatus, MemoryVersionType
from app.db.models_core import new_id, utc_now
from app.db.session import Base


class MemoryVersion(Base):
    __tablename__ = "memory_versions"
    __table_args__ = (
        UniqueConstraint("branch_id", "version_number", name="uq_memory_branch_version"),
        Index("ix_memory_branch_created", "branch_id", "version_number"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    branch_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("branches.id"), nullable=False
    )
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    type: Mapped[MemoryVersionType] = mapped_column(
        Enum(MemoryVersionType), nullable=False
    )
    base_version_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("memory_versions.id"), nullable=True
    )
    restored_from_version_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("memory_versions.id"), nullable=True
    )
    inherited_from_version_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("memory_versions.id"), nullable=True
    )
    protected_user_text: Mapped[str] = mapped_column(Text, nullable=False, default="")
    system_summary: Mapped[str] = mapped_column(Text, nullable=False, default="")
    covered_through_position: Mapped[int | None] = mapped_column(Integer, nullable=True)
    added_from_position: Mapped[int | None] = mapped_column(Integer, nullable=True)
    added_through_position: Mapped[int | None] = mapped_column(Integer, nullable=True)
    conflict_metadata_json: Mapped[dict[str, object]] = mapped_column(
        JSON, nullable=False, default=dict
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )


class MemoryUpdateRecord(Base):
    __tablename__ = "memory_update_records"
    __table_args__ = (
        Index("ix_memory_updates_branch_created", "branch_id", "created_at"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    branch_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("branches.id"), nullable=False
    )
    base_memory_version_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("memory_versions.id"), nullable=True
    )
    target_from_position: Mapped[int] = mapped_column(Integer, nullable=False)
    target_through_position: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[MemoryUpdateStatus] = mapped_column(
        Enum(MemoryUpdateStatus), nullable=False
    )
    attempt_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    error_category: Mapped[str | None] = mapped_column(String(100), nullable=True)
    error_message: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_memory_version_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("memory_versions.id"), nullable=True
    )
