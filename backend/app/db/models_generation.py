from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.enums import (
    AttemptStatus,
    ErrorCategory,
    GenerationMode,
    GenerationStatus,
    SearchStatus,
    SelectionMode,
)
from app.db.models_core import new_id, utc_now
from app.db.session import Base


class SearchSnapshot(Base):
    __tablename__ = "search_snapshots"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    user_message_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("user_messages.id"), nullable=False, unique=True
    )
    query: Mapped[str] = mapped_column(Text, nullable=False)
    provider: Mapped[str] = mapped_column(String(50), nullable=False)
    status: Mapped[SearchStatus] = mapped_column(Enum(SearchStatus), nullable=False)
    failure_code: Mapped[str | None] = mapped_column(String(100), nullable=True)
    failure_message: Mapped[str | None] = mapped_column(String(500), nullable=True)
    searched_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )
    latency_ms: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    provider_metadata_json: Mapped[dict[str, object]] = mapped_column(
        JSON, nullable=False, default=dict
    )


class SearchResult(Base):
    __tablename__ = "search_results"
    __table_args__ = (
        UniqueConstraint("search_snapshot_id", "rank", name="uq_search_result_rank"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    search_snapshot_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("search_snapshots.id"), nullable=False
    )
    rank: Mapped[int] = mapped_column(Integer, nullable=False)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    snippet: Mapped[str] = mapped_column(Text, nullable=False)
    url: Mapped[str] = mapped_column(Text, nullable=False)
    dedupe_key: Mapped[str] = mapped_column(String(200), nullable=False)


class ContextSnapshot(Base):
    __tablename__ = "context_snapshots"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    user_message_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("user_messages.id"), nullable=False
    )
    branch_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("branches.id"), nullable=False
    )
    search_snapshot_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("search_snapshots.id"), nullable=False
    )
    memory_version_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("memory_versions.id"), nullable=True
    )
    role_version_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("role_versions.id"), nullable=True
    )
    system_rules_text: Mapped[str] = mapped_column(Text, nullable=False, default="")
    role_text: Mapped[str] = mapped_column(Text, nullable=False, default="")
    protected_memory_text: Mapped[str] = mapped_column(Text, nullable=False, default="")
    system_memory_text: Mapped[str] = mapped_column(Text, nullable=False, default="")
    history_json: Mapped[list[dict[str, object]]] = mapped_column(
        JSON, nullable=False, default=list
    )
    search_context_json: Mapped[dict[str, object]] = mapped_column(
        JSON, nullable=False, default=dict
    )
    current_user_text: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )


class GenerationTask(Base):
    __tablename__ = "generation_tasks"
    __table_args__ = (Index("ix_generation_tasks_message_created", "user_message_id", "created_at"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    user_message_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("user_messages.id"), nullable=False
    )
    branch_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("branches.id"), nullable=False
    )
    generation_mode: Mapped[GenerationMode] = mapped_column(
        Enum(GenerationMode), nullable=False, default=GenerationMode.NEW_MESSAGE
    )
    selection_mode: Mapped[SelectionMode] = mapped_column(
        Enum(SelectionMode), nullable=False
    )
    source_answer_version_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("assistant_answer_versions.id"), nullable=True
    )
    requested_model_key: Mapped[str | None] = mapped_column(String(32), nullable=True)
    search_snapshot_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("search_snapshots.id"), nullable=False
    )
    context_snapshot_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("context_snapshots.id"), nullable=False, unique=True
    )
    # RouteSnapshot owns the enforced one-to-one FK; this pointer avoids a DB FK cycle.
    route_snapshot_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    status: Mapped[GenerationStatus] = mapped_column(
        Enum(GenerationStatus), nullable=False, default=GenerationStatus.PREPARING_CONTEXT
    )
    failure_category: Mapped[ErrorCategory | None] = mapped_column(
        Enum(ErrorCategory), nullable=True
    )
    failure_message: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class RouteSnapshot(Base):
    __tablename__ = "route_snapshots"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    generation_task_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("generation_tasks.id"), nullable=False, unique=True
    )
    user_message_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("user_messages.id"), nullable=False
    )
    strategy_version: Mapped[str] = mapped_column(String(100), nullable=False)
    router_provider_version: Mapped[str] = mapped_column(String(100), nullable=False)
    accuracy_weight: Mapped[Decimal] = mapped_column(Numeric(5, 4), nullable=False)
    cost_weight: Mapped[Decimal] = mapped_column(Numeric(5, 4), nullable=False)
    price_version: Mapped[str] = mapped_column(String(100), nullable=False)
    model_config_snapshot_json: Mapped[list[dict[str, object]]] = mapped_column(
        JSON, nullable=False
    )
    routing_latency_ms: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )


class RouteCandidate(Base):
    __tablename__ = "route_candidates"
    __table_args__ = (
        UniqueConstraint("route_snapshot_id", "model_key", name="uq_route_candidate_model"),
        Index("ix_route_candidate_rank", "route_snapshot_id", "rank"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    route_snapshot_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("route_snapshots.id"), nullable=False
    )
    model_key: Mapped[str] = mapped_column(String(32), nullable=False)
    display_name_snapshot: Mapped[str] = mapped_column(String(200), nullable=False)
    router_model_name_snapshot: Mapped[str] = mapped_column(String(200), nullable=False)
    eligible: Mapped[bool] = mapped_column(Boolean, nullable=False)
    ineligible_reason: Mapped[str | None] = mapped_column(String(200), nullable=True)
    predicted_accuracy: Mapped[Decimal | None] = mapped_column(Numeric(12, 10), nullable=True)
    predicted_input_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    predicted_output_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    predicted_cost: Mapped[Decimal | None] = mapped_column(Numeric(20, 10), nullable=True)
    cost_score: Mapped[Decimal | None] = mapped_column(Numeric(12, 10), nullable=True)
    route_score: Mapped[Decimal | None] = mapped_column(Numeric(12, 10), nullable=True)
    rank: Mapped[int | None] = mapped_column(Integer, nullable=True)


class GenerationAttempt(Base):
    __tablename__ = "generation_attempts"
    __table_args__ = (
        UniqueConstraint("generation_task_id", "attempt_index", name="uq_attempt_index"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    generation_task_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("generation_tasks.id"), nullable=False
    )
    attempt_index: Mapped[int] = mapped_column(Integer, nullable=False)
    model_key: Mapped[str] = mapped_column(String(32), nullable=False)
    display_name_snapshot: Mapped[str] = mapped_column(String(200), nullable=False)
    response_model_snapshot: Mapped[str | None] = mapped_column(String(200), nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ended_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    status: Mapped[AttemptStatus] = mapped_column(Enum(AttemptStatus), nullable=False)
    finish_reason: Mapped[str | None] = mapped_column(String(100), nullable=True)
    error_category: Mapped[ErrorCategory | None] = mapped_column(
        Enum(ErrorCategory), nullable=True
    )
    error_code: Mapped[str | None] = mapped_column(String(100), nullable=True)
    error_message: Mapped[str | None] = mapped_column(String(500), nullable=True)
    retry_of_attempt_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("generation_attempts.id"), nullable=True
    )
    actual_input_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    actual_output_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    charged_cost: Mapped[Decimal | None] = mapped_column(Numeric(20, 10), nullable=True)
    price_version: Mapped[str] = mapped_column(String(100), nullable=False)
    provider_request_id: Mapped[str | None] = mapped_column(String(200), nullable=True)
