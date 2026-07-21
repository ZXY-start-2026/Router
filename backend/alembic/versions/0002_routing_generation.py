"""Add iteration 2 routing and generation audit data.

Revision ID: 0002_routing_generation
Revises: 0001_core_chat
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "0002_routing_generation"
down_revision: str | None = "0001_core_chat"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("user_messages") as batch:
        batch.add_column(sa.Column("search_snapshot_id", sa.String(36), nullable=True))

    op.create_table(
        "search_snapshots",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_message_id", sa.String(36), nullable=False, unique=True),
        sa.Column("query", sa.Text(), nullable=False),
        sa.Column("provider", sa.String(50), nullable=False),
        sa.Column("status", sa.Enum("SUCCESS_WITH_RESULTS", "SUCCESS_NO_VALID_RESULTS", "FAILED", "TIMEOUT", name="searchstatus"), nullable=False),
        sa.Column("failure_code", sa.String(100), nullable=True),
        sa.Column("failure_message", sa.String(500), nullable=True),
        sa.Column("searched_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("latency_ms", sa.Integer(), nullable=False),
        sa.Column("provider_metadata_json", sa.JSON(), nullable=False),
        sa.ForeignKeyConstraint(["user_message_id"], ["user_messages.id"]),
    )
    op.create_table(
        "search_results",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("search_snapshot_id", sa.String(36), nullable=False),
        sa.Column("rank", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("snippet", sa.Text(), nullable=False),
        sa.Column("url", sa.Text(), nullable=False),
        sa.Column("dedupe_key", sa.String(200), nullable=False),
        sa.ForeignKeyConstraint(["search_snapshot_id"], ["search_snapshots.id"]),
        sa.UniqueConstraint("search_snapshot_id", "rank", name="uq_search_result_rank"),
    )
    op.create_table(
        "context_snapshots",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_message_id", sa.String(36), nullable=False),
        sa.Column("branch_id", sa.String(36), nullable=False),
        sa.Column("search_snapshot_id", sa.String(36), nullable=False),
        sa.Column("system_rules_text", sa.Text(), nullable=False),
        sa.Column("role_text", sa.Text(), nullable=False),
        sa.Column("protected_memory_text", sa.Text(), nullable=False),
        sa.Column("system_memory_text", sa.Text(), nullable=False),
        sa.Column("history_json", sa.JSON(), nullable=False),
        sa.Column("search_context_json", sa.JSON(), nullable=False),
        sa.Column("current_user_text", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_message_id"], ["user_messages.id"]),
        sa.ForeignKeyConstraint(["branch_id"], ["branches.id"]),
        sa.ForeignKeyConstraint(["search_snapshot_id"], ["search_snapshots.id"]),
    )
    op.create_table(
        "generation_tasks",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_message_id", sa.String(36), nullable=False),
        sa.Column("branch_id", sa.String(36), nullable=False),
        sa.Column("generation_mode", sa.Enum("NEW_MESSAGE", "REGENERATE", name="generationmode"), nullable=False),
        sa.Column("selection_mode", sa.Enum("AUTO_ROUTE", "AUTO_FALLBACK", "USER_SELECTED", name="selectionmode"), nullable=False),
        sa.Column("requested_model_key", sa.String(32), nullable=True),
        sa.Column("search_snapshot_id", sa.String(36), nullable=False),
        sa.Column("context_snapshot_id", sa.String(36), nullable=False, unique=True),
        sa.Column("route_snapshot_id", sa.String(36), nullable=True),
        sa.Column("status", sa.Enum("IDLE", "PREPARING_CONTEXT", "SEARCHING", "ROUTING", "GENERATING", "SUCCEEDED", "FAILED", name="generationstatus"), nullable=False),
        sa.Column("failure_category", sa.Enum("TRANSIENT_TIMEOUT", "TRANSIENT_NETWORK", "TRANSIENT_RATE_LIMIT", "TRANSIENT_SERVER", "MODEL_REQUEST_REJECTED", "MODEL_RESPONSE_INVALID", "MODEL_UNAVAILABLE", "GLOBAL_INPUT_VIOLATION", "UNKNOWN", name="errorcategory"), nullable=True),
        sa.Column("failure_message", sa.String(500), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["user_message_id"], ["user_messages.id"]),
        sa.ForeignKeyConstraint(["branch_id"], ["branches.id"]),
        sa.ForeignKeyConstraint(["search_snapshot_id"], ["search_snapshots.id"]),
        sa.ForeignKeyConstraint(["context_snapshot_id"], ["context_snapshots.id"]),
    )
    op.create_index("ix_generation_tasks_message_created", "generation_tasks", ["user_message_id", "created_at"])
    op.create_table(
        "route_snapshots",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("generation_task_id", sa.String(36), nullable=False, unique=True),
        sa.Column("user_message_id", sa.String(36), nullable=False),
        sa.Column("strategy_version", sa.String(100), nullable=False),
        sa.Column("router_provider_version", sa.String(100), nullable=False),
        sa.Column("accuracy_weight", sa.Numeric(5, 4), nullable=False),
        sa.Column("cost_weight", sa.Numeric(5, 4), nullable=False),
        sa.Column("price_version", sa.String(100), nullable=False),
        sa.Column("model_config_snapshot_json", sa.JSON(), nullable=False),
        sa.Column("routing_latency_ms", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["generation_task_id"], ["generation_tasks.id"]),
        sa.ForeignKeyConstraint(["user_message_id"], ["user_messages.id"]),
    )
    op.create_table(
        "route_candidates",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("route_snapshot_id", sa.String(36), nullable=False),
        sa.Column("model_key", sa.String(32), nullable=False),
        sa.Column("display_name_snapshot", sa.String(200), nullable=False),
        sa.Column("router_model_name_snapshot", sa.String(200), nullable=False),
        sa.Column("eligible", sa.Boolean(), nullable=False),
        sa.Column("ineligible_reason", sa.String(200), nullable=True),
        sa.Column("predicted_accuracy", sa.Numeric(12, 10), nullable=True),
        sa.Column("predicted_input_tokens", sa.Integer(), nullable=True),
        sa.Column("predicted_output_tokens", sa.Integer(), nullable=True),
        sa.Column("predicted_cost", sa.Numeric(20, 10), nullable=True),
        sa.Column("cost_score", sa.Numeric(12, 10), nullable=True),
        sa.Column("route_score", sa.Numeric(12, 10), nullable=True),
        sa.Column("rank", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(["route_snapshot_id"], ["route_snapshots.id"]),
        sa.UniqueConstraint("route_snapshot_id", "model_key", name="uq_route_candidate_model"),
    )
    op.create_index("ix_route_candidate_rank", "route_candidates", ["route_snapshot_id", "rank"])
    op.create_table(
        "generation_attempts",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("generation_task_id", sa.String(36), nullable=False),
        sa.Column("attempt_index", sa.Integer(), nullable=False),
        sa.Column("model_key", sa.String(32), nullable=False),
        sa.Column("display_name_snapshot", sa.String(200), nullable=False),
        sa.Column("response_model_snapshot", sa.String(200), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", sa.Enum("SUCCEEDED", "FAILED", name="attemptstatus"), nullable=False),
        sa.Column("finish_reason", sa.String(100), nullable=True),
        sa.Column("error_category", sa.Enum("TRANSIENT_TIMEOUT", "TRANSIENT_NETWORK", "TRANSIENT_RATE_LIMIT", "TRANSIENT_SERVER", "MODEL_REQUEST_REJECTED", "MODEL_RESPONSE_INVALID", "MODEL_UNAVAILABLE", "GLOBAL_INPUT_VIOLATION", "UNKNOWN", name="errorcategory"), nullable=True),
        sa.Column("error_code", sa.String(100), nullable=True),
        sa.Column("error_message", sa.String(500), nullable=True),
        sa.Column("retry_of_attempt_id", sa.String(36), nullable=True),
        sa.Column("actual_input_tokens", sa.Integer(), nullable=True),
        sa.Column("actual_output_tokens", sa.Integer(), nullable=True),
        sa.Column("charged_cost", sa.Numeric(20, 10), nullable=True),
        sa.Column("price_version", sa.String(100), nullable=False),
        sa.Column("provider_request_id", sa.String(200), nullable=True),
        sa.ForeignKeyConstraint(["generation_task_id"], ["generation_tasks.id"]),
        sa.ForeignKeyConstraint(["retry_of_attempt_id"], ["generation_attempts.id"]),
        sa.UniqueConstraint("generation_task_id", "attempt_index", name="uq_attempt_index"),
    )

    with op.batch_alter_table("assistant_answer_versions") as batch:
        batch.add_column(sa.Column("display_name_snapshot", sa.String(200), nullable=True))
        batch.add_column(sa.Column("generation_task_id", sa.String(36), nullable=True))
        batch.add_column(sa.Column("route_snapshot_id", sa.String(36), nullable=True))
        batch.add_column(sa.Column("predicted_input_tokens", sa.Integer(), nullable=True))
        batch.add_column(sa.Column("predicted_output_tokens", sa.Integer(), nullable=True))
        batch.add_column(sa.Column("actual_input_tokens", sa.Integer(), nullable=True))
        batch.add_column(sa.Column("actual_output_tokens", sa.Integer(), nullable=True))
        batch.add_column(sa.Column("predicted_cost", sa.Numeric(20, 10), nullable=True))
        batch.add_column(sa.Column("actual_cost", sa.Numeric(20, 10), nullable=True))
        batch.add_column(sa.Column("input_token_error", sa.Integer(), nullable=True))
        batch.add_column(sa.Column("output_token_error", sa.Integer(), nullable=True))
        batch.add_column(sa.Column("cost_error", sa.Numeric(20, 10), nullable=True))
        batch.add_column(sa.Column("price_version", sa.String(100), nullable=True))
        batch.create_unique_constraint("uq_answer_generation_task", ["generation_task_id"])
        batch.create_foreign_key("fk_answer_generation_task", "generation_tasks", ["generation_task_id"], ["id"])
        batch.create_foreign_key("fk_answer_route_snapshot", "route_snapshots", ["route_snapshot_id"], ["id"])


def downgrade() -> None:
    with op.batch_alter_table("assistant_answer_versions") as batch:
        batch.drop_constraint("fk_answer_route_snapshot", type_="foreignkey")
        batch.drop_constraint("fk_answer_generation_task", type_="foreignkey")
        batch.drop_constraint("uq_answer_generation_task", type_="unique")
        for column in ("price_version", "cost_error", "output_token_error", "input_token_error", "actual_cost", "predicted_cost", "actual_output_tokens", "actual_input_tokens", "predicted_output_tokens", "predicted_input_tokens", "route_snapshot_id", "generation_task_id", "display_name_snapshot"):
            batch.drop_column(column)
    op.drop_table("generation_attempts")
    op.drop_index("ix_route_candidate_rank", table_name="route_candidates")
    op.drop_table("route_candidates")
    op.drop_table("route_snapshots")
    op.drop_index("ix_generation_tasks_message_created", table_name="generation_tasks")
    op.drop_table("generation_tasks")
    op.drop_table("context_snapshots")
    op.drop_table("search_results")
    op.drop_table("search_snapshots")
    with op.batch_alter_table("user_messages") as batch:
        batch.drop_column("search_snapshot_id")
