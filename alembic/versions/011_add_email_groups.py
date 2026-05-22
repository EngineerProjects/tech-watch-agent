"""Add email groups and watch profile associations

Revision ID: 011
Revises: 010
Create Date: 2026-05-22
"""

from alembic import op
import sqlalchemy as sa

revision = "011"
down_revision = "010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "email_groups",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_email_groups_name", "email_groups", ["name"], unique=False)
    op.create_index("ix_email_groups_is_active", "email_groups", ["is_active"], unique=False)
    op.create_index("ix_email_groups_created_at", "email_groups", ["created_at"], unique=False)

    op.create_table(
        "email_group_recipients",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("group_id", sa.Uuid(), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("label", sa.String(length=120), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["group_id"], ["email_groups.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_email_group_recipients_group_id", "email_group_recipients", ["group_id"], unique=False)
    op.create_index(
        "ix_email_group_recipients_group_email_unique",
        "email_group_recipients",
        ["group_id", "email"],
        unique=True,
    )

    op.create_table(
        "watch_profile_email_groups",
        sa.Column("watch_profile_id", sa.Uuid(), nullable=False),
        sa.Column("email_group_id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["email_group_id"], ["email_groups.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["watch_profile_id"], ["watch_profiles.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("watch_profile_id", "email_group_id"),
    )


def downgrade() -> None:
    op.drop_table("watch_profile_email_groups")
    op.drop_index("ix_email_group_recipients_group_email_unique", table_name="email_group_recipients")
    op.drop_index("ix_email_group_recipients_group_id", table_name="email_group_recipients")
    op.drop_table("email_group_recipients")
    op.drop_index("ix_email_groups_created_at", table_name="email_groups")
    op.drop_index("ix_email_groups_is_active", table_name="email_groups")
    op.drop_index("ix_email_groups_name", table_name="email_groups")
    op.drop_table("email_groups")
