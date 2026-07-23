"""Add iteration 3 answer regeneration source and branch point constraints.

Revision ID: 0003_answer_branching
Revises: 0002_routing_generation
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "0003_answer_branching"
down_revision: str | None = "0002_routing_generation"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("generation_tasks") as batch:
        batch.add_column(
            sa.Column("source_answer_version_id", sa.String(36), nullable=True)
        )
        batch.create_foreign_key(
            "fk_generation_tasks_source_answer",
            "assistant_answer_versions",
            ["source_answer_version_id"],
            ["id"],
        )

    with op.batch_alter_table("branches") as batch:
        batch.create_foreign_key(
            "fk_branches_point_message",
            "user_messages",
            ["branch_point_message_id"],
            ["id"],
        )
        batch.create_foreign_key(
            "fk_branches_point_answer",
            "assistant_answer_versions",
            ["branch_point_answer_version_id"],
            ["id"],
        )


def downgrade() -> None:
    with op.batch_alter_table("branches") as batch:
        batch.drop_constraint("fk_branches_point_answer", type_="foreignkey")
        batch.drop_constraint("fk_branches_point_message", type_="foreignkey")

    with op.batch_alter_table("generation_tasks") as batch:
        batch.drop_constraint("fk_generation_tasks_source_answer", type_="foreignkey")
        batch.drop_column("source_answer_version_id")
