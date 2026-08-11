"""add immutable expense policy history

Revision ID: 20260810_0005
Revises: 20260731_0004
Create Date: 2026-08-10
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260810_0005"
down_revision: str | None = "20260731_0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "expense_policy_versions",
        sa.Column("snapshot_id", sa.String(length=40), nullable=False),
        sa.Column("mission_id", sa.String(length=40), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("based_on_snapshot_id", sa.String(length=40), nullable=True),
        sa.Column("source_event_id", sa.String(length=120), nullable=True),
        sa.Column("policy_id", sa.String(length=80), nullable=False),
        sa.Column("policy_version", sa.String(length=40), nullable=False),
        sa.Column("allowed_rail_classes", sa.JSON(), nullable=False),
        sa.Column("allowed_flight_classes", sa.JSON(), nullable=False),
        sa.Column("hotel_nightly_cap_yuan", sa.Integer(), nullable=False),
        sa.Column("meal_daily_cap_yuan", sa.Integer(), nullable=False),
        sa.Column("local_transport_daily_cap_yuan", sa.Integer(), nullable=False),
        sa.Column("trip_total_cap_yuan", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["mission_id"], ["missions.mission_id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("snapshot_id"),
        sa.UniqueConstraint(
            "mission_id", "sequence", name="uq_expense_policy_version_sequence"
        ),
        sa.UniqueConstraint(
            "source_event_id", name="uq_expense_policy_source_event"
        ),
    )
    op.create_index(
        "ix_expense_policy_versions_mission_id",
        "expense_policy_versions",
        ["mission_id"],
    )
    op.execute(
        sa.text(
            """
            INSERT INTO expense_policy_versions (
                snapshot_id, mission_id, sequence, based_on_snapshot_id,
                source_event_id, policy_id, policy_version,
                allowed_rail_classes, allowed_flight_classes,
                hotel_nightly_cap_yuan, meal_daily_cap_yuan,
                local_transport_daily_cap_yuan, trip_total_cap_yuan, created_at
            )
            SELECT
                snapshot_id, mission_id, 1, NULL, NULL, policy_id, policy_version,
                allowed_rail_classes, allowed_flight_classes,
                hotel_nightly_cap_yuan, meal_daily_cap_yuan,
                local_transport_daily_cap_yuan, trip_total_cap_yuan, created_at
            FROM expense_policy_snapshots
            """
        )
    )


def downgrade() -> None:
    op.drop_index(
        "ix_expense_policy_versions_mission_id",
        table_name="expense_policy_versions",
    )
    op.drop_table("expense_policy_versions")
