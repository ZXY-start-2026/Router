"""Create iteration 1 core chat tables.

Revision ID: 0001_core_chat
Revises:
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "0001_core_chat"
down_revision: str | None = None
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "conversations",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column(
            "title_source",
            sa.Enum("DEFAULT", "AUTO_FIRST_MESSAGE", "USER_EDIT", name="titlesource"),
            nullable=False,
        ),
        sa.Column("active_branch_id", sa.String(length=36), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_conversations_updated_id", "conversations", ["updated_at", "id"]
    )
    op.create_table(
        "branches",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("conversation_id", sa.String(length=36), nullable=False),
        sa.Column("parent_branch_id", sa.String(length=36), nullable=True),
        sa.Column(
            "branch_point_type",
            sa.Enum(
                "ROOT",
                "USER_MESSAGE_EDIT",
                "ANSWER_VERSION_ACTIVATE",
                name="branchpointtype",
            ),
            nullable=False,
        ),
        sa.Column("branch_point_message_id", sa.String(length=36), nullable=True),
        sa.Column("branch_point_answer_version_id", sa.String(length=36), nullable=True),
        sa.Column("complete_turn_count", sa.Integer(), nullable=False),
        sa.Column(
            "status",
            sa.Enum("ACTIVE", "ARCHIVED", name="branchstatus"),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["conversation_id"], ["conversations.id"]),
        sa.ForeignKeyConstraint(["parent_branch_id"], ["branches.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_branches_conversation_created", "branches", ["conversation_id", "created_at"]
    )
    with op.batch_alter_table("conversations") as batch_op:
        batch_op.create_foreign_key(
            "fk_conversations_active_branch", "branches", ["active_branch_id"], ["id"]
        )
    op.create_table(
        "user_messages",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                "PENDING",
                "HAS_ACTIVE_ANSWER",
                "GENERATION_FAILED",
                name="usermessagestatus",
            ),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "assistant_answer_versions",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("user_message_id", sa.String(length=36), nullable=False),
        sa.Column("model_key", sa.String(length=32), nullable=True),
        sa.Column("model_id_snapshot", sa.String(length=200), nullable=True),
        sa.Column(
            "selection_mode",
            sa.Enum("AUTO_ROUTE", "AUTO_FALLBACK", "USER_SELECTED", name="selectionmode"),
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.Enum(
                "GENERATING",
                "SUCCEEDED_ACTIVE",
                "SUCCEEDED_INACTIVE",
                "FAILED",
                "STOPPED",
                name="answerversionstatus",
            ),
            nullable=False,
        ),
        sa.Column("content", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["user_message_id"], ["user_messages.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_answers_message_created",
        "assistant_answer_versions",
        ["user_message_id", "created_at"],
    )
    op.create_table(
        "branch_messages",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("branch_id", sa.String(length=36), nullable=False),
        sa.Column("user_message_id", sa.String(length=36), nullable=False),
        sa.Column("logical_position", sa.Integer(), nullable=False),
        sa.Column("active_answer_version_id", sa.String(length=36), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["active_answer_version_id"], ["assistant_answer_versions.id"]),
        sa.ForeignKeyConstraint(["branch_id"], ["branches.id"]),
        sa.ForeignKeyConstraint(["user_message_id"], ["user_messages.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("branch_id", "logical_position", name="uq_branch_message_position"),
        sa.UniqueConstraint("branch_id", "user_message_id", name="uq_branch_user_message"),
    )
    op.create_index(
        "ix_branch_messages_order", "branch_messages", ["branch_id", "logical_position"]
    )


def downgrade() -> None:
    op.drop_index("ix_branch_messages_order", table_name="branch_messages")
    op.drop_table("branch_messages")
    op.drop_index("ix_answers_message_created", table_name="assistant_answer_versions")
    op.drop_table("assistant_answer_versions")
    op.drop_table("user_messages")
    with op.batch_alter_table("conversations") as batch_op:
        batch_op.drop_constraint("fk_conversations_active_branch", type_="foreignkey")
    op.drop_index("ix_branches_conversation_created", table_name="branches")
    op.drop_table("branches")
    op.drop_index("ix_conversations_updated_id", table_name="conversations")
    op.drop_table("conversations")

