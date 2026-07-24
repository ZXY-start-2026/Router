"""Add iteration 5 role templates and immutable versions.

Revision ID: 0005_roles
Revises: 0004_memory
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "0005_roles"
down_revision: str | None = "0004_memory"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "role_templates",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("persona", sa.Text(), nullable=False),
        sa.Column("background", sa.Text(), nullable=False),
        sa.Column("domain", sa.Text(), nullable=False),
        sa.Column("traits_json", sa.JSON(), nullable=False),
        sa.Column("style", sa.Text(), nullable=False),
        sa.Column("constraints_text", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_role_templates_created", "role_templates", ["created_at", "id"]
    )
    op.create_table(
        "role_versions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("conversation_id", sa.String(36), nullable=False),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("source_template_id", sa.String(36), nullable=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("persona", sa.Text(), nullable=False),
        sa.Column("background", sa.Text(), nullable=False),
        sa.Column("domain", sa.Text(), nullable=False),
        sa.Column("traits_json", sa.JSON(), nullable=False),
        sa.Column("style", sa.Text(), nullable=False),
        sa.Column("constraints_text", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["conversation_id"], ["conversations.id"]),
        sa.ForeignKeyConstraint(["source_template_id"], ["role_templates.id"]),
        sa.UniqueConstraint(
            "conversation_id", "version_number", name="uq_role_conversation_version"
        ),
    )
    op.create_index(
        "ix_role_versions_conversation",
        "role_versions",
        ["conversation_id", "version_number"],
    )
    with op.batch_alter_table("branches") as batch:
        batch.add_column(sa.Column("active_role_version_id", sa.String(36), nullable=True))
        batch.create_foreign_key(
            "fk_branches_active_role",
            "role_versions",
            ["active_role_version_id"],
            ["id"],
        )
    with op.batch_alter_table("context_snapshots") as batch:
        batch.add_column(sa.Column("role_version_id", sa.String(36), nullable=True))
        batch.create_foreign_key(
            "fk_context_role_version",
            "role_versions",
            ["role_version_id"],
            ["id"],
        )


def downgrade() -> None:
    with op.batch_alter_table("context_snapshots") as batch:
        batch.drop_constraint("fk_context_role_version", type_="foreignkey")
        batch.drop_column("role_version_id")
    with op.batch_alter_table("branches") as batch:
        batch.drop_constraint("fk_branches_active_role", type_="foreignkey")
        batch.drop_column("active_role_version_id")
    op.drop_index("ix_role_versions_conversation", table_name="role_versions")
    op.drop_table("role_versions")
    op.drop_index("ix_role_templates_created", table_name="role_templates")
    op.drop_table("role_templates")
