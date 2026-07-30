"""create FieldPilot v1 mission domain

Revision ID: 20260730_0001
Revises:
Create Date: 2026-07-30
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260730_0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "missions",
        sa.Column("mission_id", sa.String(length=40), nullable=False),
        sa.Column("origin_name", sa.String(length=120), nullable=False),
        sa.Column("origin_address", sa.String(length=240), nullable=False),
        sa.Column("origin_city", sa.String(length=40), nullable=False),
        sa.Column("origin_longitude", sa.Float(), nullable=True),
        sa.Column("origin_latitude", sa.Float(), nullable=True),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=False),
        sa.Column("timezone", sa.String(length=64), nullable=False),
        sa.Column("urgency", sa.String(length=20), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("active_revision", sa.Integer(), nullable=True),
        sa.Column("transport_preferences", sa.JSON(), nullable=False),
        sa.Column("notes", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("mission_id"),
    )
    op.create_table(
        "expense_policy_snapshots",
        sa.Column("snapshot_id", sa.String(length=40), nullable=False),
        sa.Column("mission_id", sa.String(length=40), nullable=False),
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
        sa.UniqueConstraint("mission_id"),
    )
    op.create_table(
        "visit_tasks",
        sa.Column("task_id", sa.String(length=40), nullable=False),
        sa.Column("mission_id", sa.String(length=40), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("location_name", sa.String(length=120), nullable=False),
        sa.Column("location_address", sa.String(length=240), nullable=False),
        sa.Column("location_city", sa.String(length=40), nullable=False),
        sa.Column("longitude", sa.Float(), nullable=True),
        sa.Column("latitude", sa.Float(), nullable=True),
        sa.Column("window_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("window_end", sa.DateTime(timezone=True), nullable=False),
        sa.Column("duration_minutes", sa.Integer(), nullable=False),
        sa.Column("priority", sa.String(length=20), nullable=False),
        sa.Column("locked", sa.Boolean(), nullable=False),
        sa.Column("completed", sa.Boolean(), nullable=False),
        sa.Column("notes", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(
            ["mission_id"], ["missions.mission_id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("task_id"),
        sa.UniqueConstraint(
            "mission_id", "position", name="uq_visit_mission_position"
        ),
    )
    op.create_index("ix_visit_tasks_mission_id", "visit_tasks", ["mission_id"])
    op.create_table(
        "plan_revisions",
        sa.Column("revision_id", sa.String(length=40), nullable=False),
        sa.Column("mission_id", sa.String(length=40), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("based_on_revision", sa.Integer(), nullable=True),
        sa.Column("request_id", sa.String(length=120), nullable=False),
        sa.Column("input_event_id", sa.String(length=120), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("plan_payload", sa.JSON(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["mission_id"], ["missions.mission_id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("revision_id"),
        sa.UniqueConstraint(
            "mission_id", "revision", name="uq_plan_mission_revision"
        ),
        sa.UniqueConstraint(
            "mission_id", "request_id", name="uq_plan_mission_request"
        ),
    )
    op.create_index(
        "ix_plan_revisions_mission_id", "plan_revisions", ["mission_id"]
    )
    op.create_table(
        "replan_events",
        sa.Column("event_id", sa.String(length=120), nullable=False),
        sa.Column("mission_id", sa.String(length=40), nullable=False),
        sa.Column("event_type", sa.String(length=40), nullable=False),
        sa.Column("based_on_revision", sa.Integer(), nullable=True),
        sa.Column("event_payload", sa.JSON(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["mission_id"], ["missions.mission_id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("event_id"),
    )
    op.create_index(
        "ix_replan_events_mission_id", "replan_events", ["mission_id"]
    )
    op.create_table(
        "provider_snapshots",
        sa.Column("snapshot_id", sa.String(length=40), nullable=False),
        sa.Column("mission_id", sa.String(length=40), nullable=False),
        sa.Column("provider", sa.String(length=60), nullable=False),
        sa.Column("capability", sa.String(length=60), nullable=False),
        sa.Column("source_mode", sa.String(length=20), nullable=False),
        sa.Column("query_fingerprint", sa.String(length=128), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("fetched_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["mission_id"], ["missions.mission_id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("snapshot_id"),
    )
    op.create_index(
        "ix_provider_snapshots_mission_id",
        "provider_snapshots",
        ["mission_id"],
    )
    op.create_index(
        "ix_provider_snapshots_query_fingerprint",
        "provider_snapshots",
        ["query_fingerprint"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_provider_snapshots_query_fingerprint",
        table_name="provider_snapshots",
    )
    op.drop_index("ix_provider_snapshots_mission_id", table_name="provider_snapshots")
    op.drop_table("provider_snapshots")
    op.drop_index("ix_replan_events_mission_id", table_name="replan_events")
    op.drop_table("replan_events")
    op.drop_index("ix_plan_revisions_mission_id", table_name="plan_revisions")
    op.drop_table("plan_revisions")
    op.drop_index("ix_visit_tasks_mission_id", table_name="visit_tasks")
    op.drop_table("visit_tasks")
    op.drop_table("expense_policy_snapshots")
    op.drop_table("missions")
