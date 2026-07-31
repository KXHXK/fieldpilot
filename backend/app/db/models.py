from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class MissionRecord(Base):
    __tablename__ = "missions"

    mission_id: Mapped[str] = mapped_column(String(40), primary_key=True)
    origin_name: Mapped[str] = mapped_column(String(120))
    origin_address: Mapped[str] = mapped_column(String(240))
    origin_city: Mapped[str] = mapped_column(String(40))
    origin_longitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    origin_latitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    start_date: Mapped[date] = mapped_column(Date)
    end_date: Mapped[date] = mapped_column(Date)
    timezone: Mapped[str] = mapped_column(String(64), default="Asia/Shanghai")
    urgency: Mapped[str] = mapped_column(String(20))
    status: Mapped[str] = mapped_column(String(30), default="draft")
    active_revision: Mapped[int | None] = mapped_column(Integer, nullable=True)
    transport_preferences: Mapped[dict[str, Any]] = mapped_column(JSON)
    notes: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )

    visits: Mapped[list[VisitTaskRecord]] = relationship(
        back_populates="mission",
        cascade="all, delete-orphan",
        lazy="selectin",
        order_by="VisitTaskRecord.position",
    )
    expense_policy: Mapped[ExpensePolicySnapshotRecord] = relationship(
        back_populates="mission",
        cascade="all, delete-orphan",
        lazy="selectin",
        uselist=False,
    )
    revisions: Mapped[list[PlanRevisionRecord]] = relationship(
        back_populates="mission",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    events: Mapped[list[ReplanEventRecord]] = relationship(
        back_populates="mission",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    provider_snapshots: Mapped[list[ProviderSnapshotRecord]] = relationship(
        back_populates="mission",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    execution_checkpoint: Mapped[ExecutionCheckpointRecord | None] = relationship(
        back_populates="mission",
        cascade="all, delete-orphan",
        lazy="selectin",
        uselist=False,
    )
    execution_commands: Mapped[list[ExecutionCommandRecord]] = relationship(
        back_populates="mission",
        cascade="all, delete-orphan",
        lazy="selectin",
    )


class VisitTaskRecord(Base):
    __tablename__ = "visit_tasks"
    __table_args__ = (
        UniqueConstraint("mission_id", "position", name="uq_visit_mission_position"),
    )

    task_id: Mapped[str] = mapped_column(String(40), primary_key=True)
    mission_id: Mapped[str] = mapped_column(
        ForeignKey("missions.mission_id", ondelete="CASCADE"), index=True
    )
    position: Mapped[int] = mapped_column(Integer)
    name: Mapped[str] = mapped_column(String(120))
    location_name: Mapped[str] = mapped_column(String(120))
    location_address: Mapped[str] = mapped_column(String(240))
    location_city: Mapped[str] = mapped_column(String(40))
    longitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    latitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    window_start: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    window_end: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    duration_minutes: Mapped[int] = mapped_column(Integer)
    priority: Mapped[str] = mapped_column(String(20))
    locked: Mapped[bool] = mapped_column(Boolean, default=False)
    completed: Mapped[bool] = mapped_column(Boolean, default=False)
    notes: Mapped[str] = mapped_column(Text, default="")

    mission: Mapped[MissionRecord] = relationship(back_populates="visits")


class ExpensePolicySnapshotRecord(Base):
    __tablename__ = "expense_policy_snapshots"

    snapshot_id: Mapped[str] = mapped_column(String(40), primary_key=True)
    mission_id: Mapped[str] = mapped_column(
        ForeignKey("missions.mission_id", ondelete="CASCADE"),
        unique=True,
    )
    policy_id: Mapped[str] = mapped_column(String(80))
    policy_version: Mapped[str] = mapped_column(String(40))
    allowed_rail_classes: Mapped[list[str]] = mapped_column(JSON)
    allowed_flight_classes: Mapped[list[str]] = mapped_column(JSON)
    hotel_nightly_cap_yuan: Mapped[int] = mapped_column(Integer)
    meal_daily_cap_yuan: Mapped[int] = mapped_column(Integer)
    local_transport_daily_cap_yuan: Mapped[int] = mapped_column(Integer)
    trip_total_cap_yuan: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now
    )

    mission: Mapped[MissionRecord] = relationship(back_populates="expense_policy")


class PlanRevisionRecord(Base):
    __tablename__ = "plan_revisions"
    __table_args__ = (
        UniqueConstraint("mission_id", "revision", name="uq_plan_mission_revision"),
        UniqueConstraint(
            "mission_id", "request_id", name="uq_plan_mission_request"
        ),
    )

    revision_id: Mapped[str] = mapped_column(String(40), primary_key=True)
    mission_id: Mapped[str] = mapped_column(
        ForeignKey("missions.mission_id", ondelete="CASCADE"), index=True
    )
    revision: Mapped[int] = mapped_column(Integer)
    based_on_revision: Mapped[int | None] = mapped_column(Integer, nullable=True)
    request_id: Mapped[str] = mapped_column(String(120))
    input_event_id: Mapped[str | None] = mapped_column(String(120), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="proposed")
    plan_payload: Mapped[dict[str, Any]] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now
    )

    mission: Mapped[MissionRecord] = relationship(back_populates="revisions")


class ReplanEventRecord(Base):
    __tablename__ = "replan_events"

    event_id: Mapped[str] = mapped_column(String(120), primary_key=True)
    mission_id: Mapped[str] = mapped_column(
        ForeignKey("missions.mission_id", ondelete="CASCADE"), index=True
    )
    event_type: Mapped[str] = mapped_column(String(40))
    based_on_revision: Mapped[int | None] = mapped_column(Integer, nullable=True)
    event_payload: Mapped[dict[str, Any]] = mapped_column(JSON)
    application_status: Mapped[str] = mapped_column(
        String(20), default="recorded_only"
    )
    changed_fields: Mapped[list[dict[str, Any]] | None] = mapped_column(
        JSON, nullable=True
    )
    applied_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now
    )

    mission: Mapped[MissionRecord] = relationship(back_populates="events")


class ProviderSnapshotRecord(Base):
    __tablename__ = "provider_snapshots"

    snapshot_id: Mapped[str] = mapped_column(String(40), primary_key=True)
    mission_id: Mapped[str] = mapped_column(
        ForeignKey("missions.mission_id", ondelete="CASCADE"), index=True
    )
    provider: Mapped[str] = mapped_column(String(60))
    capability: Mapped[str] = mapped_column(String(60))
    source_mode: Mapped[str] = mapped_column(String(20))
    query_fingerprint: Mapped[str] = mapped_column(String(128), index=True)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON)
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    mission: Mapped[MissionRecord] = relationship(back_populates="provider_snapshots")


class AgentRunRecord(Base):
    __tablename__ = "agent_runs"

    trace_id: Mapped[str] = mapped_column(String(40), primary_key=True)
    request_id: Mapped[str] = mapped_column(String(120), unique=True)
    capability: Mapped[str] = mapped_column(String(60))
    input_fingerprint: Mapped[str] = mapped_column(String(64), index=True)
    reference_date: Mapped[date] = mapped_column(Date)
    timezone: Mapped[str] = mapped_column(String(64))
    mode: Mapped[str] = mapped_column(String(20))
    model: Mapped[str] = mapped_column(String(120))
    prompt_version: Mapped[str] = mapped_column(String(60))
    status: Mapped[str] = mapped_column(String(30))
    output_payload: Mapped[dict[str, Any]] = mapped_column(JSON)
    usage_payload: Mapped[dict[str, Any]] = mapped_column(JSON)
    latency_ms: Mapped[float] = mapped_column(Float)
    failure_type: Mapped[str | None] = mapped_column(String(120), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class ExecutionCheckpointRecord(Base):
    __tablename__ = "execution_checkpoints"

    mission_id: Mapped[str] = mapped_column(
        ForeignKey("missions.mission_id", ondelete="CASCADE"), primary_key=True
    )
    version: Mapped[int] = mapped_column(Integer, default=0)
    source_revision: Mapped[int] = mapped_column(Integer)
    locked_through_segment_id: Mapped[str | None] = mapped_column(
        String(80), nullable=True
    )
    locked_through_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    completed_through_segment_id: Mapped[str | None] = mapped_column(
        String(80), nullable=True
    )
    completed_through_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    protected_segments: Mapped[list[dict[str, Any]]] = mapped_column(
        JSON, default=list
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )

    mission: Mapped[MissionRecord] = relationship(
        back_populates="execution_checkpoint"
    )

    __mapper_args__ = {
        "version_id_col": version,
        "version_id_generator": False,
    }


class ExecutionCommandRecord(Base):
    __tablename__ = "execution_commands"

    command_id: Mapped[str] = mapped_column(String(120), primary_key=True)
    mission_id: Mapped[str] = mapped_column(
        ForeignKey("missions.mission_id", ondelete="CASCADE"), index=True
    )
    based_on_revision: Mapped[int] = mapped_column(Integer)
    expected_version: Mapped[int] = mapped_column(Integer)
    action: Mapped[str] = mapped_column(String(30))
    through_segment_id: Mapped[str] = mapped_column(String(80))
    result_payload: Mapped[dict[str, Any]] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now
    )

    mission: Mapped[MissionRecord] = relationship(back_populates="execution_commands")
