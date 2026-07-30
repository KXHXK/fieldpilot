"""add auditable agent runs

Revision ID: 20260730_0002
Revises: 20260730_0001
Create Date: 2026-07-30
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260730_0002"
down_revision: str | None = "20260730_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "agent_runs",
        sa.Column("trace_id", sa.String(length=40), nullable=False),
        sa.Column("request_id", sa.String(length=120), nullable=False),
        sa.Column("capability", sa.String(length=60), nullable=False),
        sa.Column("input_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("reference_date", sa.Date(), nullable=False),
        sa.Column("timezone", sa.String(length=64), nullable=False),
        sa.Column("mode", sa.String(length=20), nullable=False),
        sa.Column("model", sa.String(length=120), nullable=False),
        sa.Column("prompt_version", sa.String(length=60), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("output_payload", sa.JSON(), nullable=False),
        sa.Column("usage_payload", sa.JSON(), nullable=False),
        sa.Column("latency_ms", sa.Float(), nullable=False),
        sa.Column("failure_type", sa.String(length=120), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.PrimaryKeyConstraint("trace_id"),
        sa.UniqueConstraint("request_id"),
    )
    op.create_index("ix_agent_runs_input_fingerprint", "agent_runs", ["input_fingerprint"])


def downgrade() -> None:
    op.drop_index("ix_agent_runs_input_fingerprint", table_name="agent_runs")
    op.drop_table("agent_runs")
