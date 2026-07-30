"""track replan event application

Revision ID: 20260730_0003
Revises: 20260730_0002
Create Date: 2026-07-30
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260730_0003"
down_revision: str | None = "20260730_0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "replan_events",
        sa.Column(
            "application_status",
            sa.String(length=20),
            server_default="recorded_only",
            nullable=False,
        ),
    )
    op.add_column(
        "replan_events", sa.Column("changed_fields", sa.JSON(), nullable=True)
    )
    op.add_column(
        "replan_events",
        sa.Column("applied_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("replan_events", "applied_at")
    op.drop_column("replan_events", "changed_fields")
    op.drop_column("replan_events", "application_status")
