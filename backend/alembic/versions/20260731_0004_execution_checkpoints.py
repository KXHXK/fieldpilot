"""add execution checkpoints and idempotent commands

Revision ID: 20260731_0004
Revises: 20260730_0003
Create Date: 2026-07-31
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260731_0004"
down_revision: str | None = "20260730_0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "execution_checkpoints",
        sa.Column("mission_id", sa.String(length=40), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("source_revision", sa.Integer(), nullable=False),
        sa.Column("locked_through_segment_id", sa.String(length=80), nullable=True),
        sa.Column("locked_through_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_through_segment_id", sa.String(length=80), nullable=True),
        sa.Column("completed_through_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("protected_segments", sa.JSON(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["mission_id"], ["missions.mission_id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("mission_id"),
    )
    op.create_table(
        "execution_commands",
        sa.Column("command_id", sa.String(length=120), nullable=False),
        sa.Column("mission_id", sa.String(length=40), nullable=False),
        sa.Column("based_on_revision", sa.Integer(), nullable=False),
        sa.Column("expected_version", sa.Integer(), nullable=False),
        sa.Column("action", sa.String(length=30), nullable=False),
        sa.Column("through_segment_id", sa.String(length=80), nullable=False),
        sa.Column("result_payload", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["mission_id"], ["missions.mission_id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("command_id"),
    )
    op.create_index(
        "ix_execution_commands_mission_id",
        "execution_commands",
        ["mission_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_execution_commands_mission_id", table_name="execution_commands"
    )
    op.drop_table("execution_commands")
    op.drop_table("execution_checkpoints")
