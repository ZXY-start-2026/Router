"""Add iteration 4 branch memory versions.

Revision ID: 0004_memory
Revises: 0003_answer_branching
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "0004_memory"
down_revision: str | None = "0003_answer_branching"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "memory_versions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("branch_id", sa.String(36), nullable=False),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column(
            "type",
            sa.Enum(
                "INITIAL_SYSTEM_SUMMARY",
                "INCREMENTAL_SYSTEM_UPDATE",
                "USER_EDIT",
                "RESTORE",
                "BRANCH_INHERIT",
                name="memoryversiontype",
            ),
            nullable=False,
        ),
        sa.Column("base_version_id", sa.String(36), nullable=True),
        sa.Column("restored_from_version_id", sa.String(36), nullable=True),
        sa.Column("inherited_from_version_id", sa.String(36), nullable=True),
        sa.Column("protected_user_text", sa.Text(), nullable=False),
        sa.Column("system_summary", sa.Text(), nullable=False),
        sa.Column("covered_through_position", sa.Integer(), nullable=True),
        sa.Column("added_from_position", sa.Integer(), nullable=True),
        sa.Column("added_through_position", sa.Integer(), nullable=True),
        sa.Column("conflict_metadata_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["branch_id"], ["branches.id"]),
        sa.ForeignKeyConstraint(["base_version_id"], ["memory_versions.id"]),
        sa.ForeignKeyConstraint(["restored_from_version_id"], ["memory_versions.id"]),
        sa.ForeignKeyConstraint(["inherited_from_version_id"], ["memory_versions.id"]),
        sa.UniqueConstraint("branch_id", "version_number", name="uq_memory_branch_version"),
    )
    op.create_index(
        "ix_memory_branch_created",
        "memory_versions",
        ["branch_id", "version_number"],
    )
    op.create_table(
        "memory_update_records",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("branch_id", sa.String(36), nullable=False),
        sa.Column("base_memory_version_id", sa.String(36), nullable=True),
        sa.Column("target_from_position", sa.Integer(), nullable=False),
        sa.Column("target_through_position", sa.Integer(), nullable=False),
        sa.Column(
            "status",
            sa.Enum("RUNNING", "SUCCEEDED", "FAILED", name="memoryupdatestatus"),
            nullable=False,
        ),
        sa.Column("attempt_count", sa.Integer(), nullable=False),
        sa.Column("error_category", sa.String(100), nullable=True),
        sa.Column("error_message", sa.String(500), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_memory_version_id", sa.String(36), nullable=True),
        sa.ForeignKeyConstraint(["branch_id"], ["branches.id"]),
        sa.ForeignKeyConstraint(["base_memory_version_id"], ["memory_versions.id"]),
        sa.ForeignKeyConstraint(["created_memory_version_id"], ["memory_versions.id"]),
    )
    op.create_index(
        "ix_memory_updates_branch_created",
        "memory_update_records",
        ["branch_id", "created_at"],
    )
    with op.batch_alter_table("branches") as batch:
        batch.add_column(sa.Column("active_memory_version_id", sa.String(36), nullable=True))
        batch.create_foreign_key(
            "fk_branches_active_memory",
            "memory_versions",
            ["active_memory_version_id"],
            ["id"],
        )
    with op.batch_alter_table("context_snapshots") as batch:
        batch.add_column(sa.Column("memory_version_id", sa.String(36), nullable=True))
        batch.create_foreign_key(
            "fk_context_memory_version",
            "memory_versions",
            ["memory_version_id"],
            ["id"],
        )


def downgrade() -> None:
    with op.batch_alter_table("context_snapshots") as batch:
        batch.drop_constraint("fk_context_memory_version", type_="foreignkey")
        batch.drop_column("memory_version_id")
    with op.batch_alter_table("branches") as batch:
        batch.drop_constraint("fk_branches_active_memory", type_="foreignkey")
        batch.drop_column("active_memory_version_id")
    op.drop_index("ix_memory_updates_branch_created", table_name="memory_update_records")
    op.drop_table("memory_update_records")
    op.drop_index("ix_memory_branch_created", table_name="memory_versions")
    op.drop_table("memory_versions")
