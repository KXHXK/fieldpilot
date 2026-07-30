from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.models import (
    ExpensePolicySnapshotRecord,
    MissionRecord,
    ReplanEventRecord,
    VisitTaskRecord,
)
from app.domain import (
    ExpensePolicyRead,
    LocationInput,
    MissionCreate,
    MissionRead,
    MissionStatus,
    ReplanEventCreate,
    ReplanEventRead,
    TransportPreferences,
    Urgency,
    VisitPriority,
    VisitTaskRead,
)


class MissionNotFoundError(LookupError):
    pass


class RevisionConflictError(RuntimeError):
    def __init__(self, expected: int | None, actual: int | None) -> None:
        self.expected = expected
        self.actual = actual
        super().__init__(f"计划版本冲突：请求基于 {expected}，当前版本为 {actual}")


class EventConflictError(RuntimeError):
    pass


def _new_id(prefix: str) -> str:
    return f"{prefix}-{uuid4().hex[:20]}"


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _mission_query(mission_id: str):
    return (
        select(MissionRecord)
        .where(MissionRecord.mission_id == mission_id)
        .options(
            selectinload(MissionRecord.visits),
            selectinload(MissionRecord.expense_policy),
        )
    )


async def create_mission(
    session: AsyncSession,
    command: MissionCreate,
) -> MissionRead:
    mission_id = _new_id("msn")
    mission = MissionRecord(
        mission_id=mission_id,
        origin_name=command.origin.name,
        origin_address=command.origin.address,
        origin_city=command.origin.city,
        origin_longitude=command.origin.longitude,
        origin_latitude=command.origin.latitude,
        start_date=command.start_date,
        end_date=command.end_date,
        timezone=command.timezone,
        urgency=command.urgency.value,
        status=MissionStatus.DRAFT.value,
        active_revision=None,
        transport_preferences=command.transport_preferences.model_dump(mode="json"),
        notes=command.notes,
    )
    mission.visits = [
        VisitTaskRecord(
            task_id=_new_id("tsk"),
            mission_id=mission_id,
            position=position,
            name=visit.name,
            location_name=visit.location.name,
            location_address=visit.location.address,
            location_city=visit.location.city,
            longitude=visit.location.longitude,
            latitude=visit.location.latitude,
            window_start=_as_utc(visit.window_start),
            window_end=_as_utc(visit.window_end),
            duration_minutes=visit.duration_minutes,
            priority=visit.priority.value,
            locked=visit.locked,
            completed=False,
            notes=visit.notes,
        )
        for position, visit in enumerate(command.visits, start=1)
    ]
    policy = command.expense_policy
    mission.expense_policy = ExpensePolicySnapshotRecord(
        snapshot_id=_new_id("pol"),
        mission_id=mission_id,
        policy_id=policy.policy_id,
        policy_version=policy.policy_version,
        allowed_rail_classes=policy.allowed_rail_classes,
        allowed_flight_classes=policy.allowed_flight_classes,
        hotel_nightly_cap_yuan=policy.hotel_nightly_cap_yuan,
        meal_daily_cap_yuan=policy.meal_daily_cap_yuan,
        local_transport_daily_cap_yuan=policy.local_transport_daily_cap_yuan,
        trip_total_cap_yuan=policy.trip_total_cap_yuan,
    )
    session.add(mission)
    await session.commit()
    return await get_mission(session, mission_id)


async def get_mission(session: AsyncSession, mission_id: str) -> MissionRead:
    result = await session.execute(_mission_query(mission_id))
    mission = result.scalar_one_or_none()
    if mission is None:
        raise MissionNotFoundError(mission_id)
    return _to_mission_read(mission)


async def record_replan_event(
    session: AsyncSession,
    mission_id: str,
    command: ReplanEventCreate,
) -> ReplanEventRead:
    mission_result = await session.execute(
        select(MissionRecord).where(MissionRecord.mission_id == mission_id)
    )
    mission = mission_result.scalar_one_or_none()
    if mission is None:
        raise MissionNotFoundError(mission_id)

    existing = await session.get(ReplanEventRecord, command.event_id)
    if existing is not None:
        if existing.mission_id != mission_id:
            raise EventConflictError("event_id 已被其他任务使用")
        return _to_event_read(existing, idempotent_replay=True)

    if command.based_on_revision != mission.active_revision:
        raise RevisionConflictError(command.based_on_revision, mission.active_revision)

    event = ReplanEventRecord(
        event_id=command.event_id,
        mission_id=mission_id,
        event_type=command.event_type.value,
        based_on_revision=command.based_on_revision,
        event_payload=command.payload,
    )
    session.add(event)
    try:
        await session.commit()
    except IntegrityError:
        await session.rollback()
        existing = await session.get(ReplanEventRecord, command.event_id)
        if existing is None or existing.mission_id != mission_id:
            raise EventConflictError("event_id 并发冲突") from None
        return _to_event_read(existing, idempotent_replay=True)
    await session.refresh(event)
    return _to_event_read(event, idempotent_replay=False)


def _to_mission_read(mission: MissionRecord) -> MissionRead:
    policy = mission.expense_policy
    return MissionRead(
        mission_id=mission.mission_id,
        origin=LocationInput(
            name=mission.origin_name,
            address=mission.origin_address,
            city=mission.origin_city,
            longitude=mission.origin_longitude,
            latitude=mission.origin_latitude,
        ),
        start_date=mission.start_date,
        end_date=mission.end_date,
        timezone=mission.timezone,
        urgency=Urgency(mission.urgency),
        status=MissionStatus(mission.status),
        active_revision=mission.active_revision,
        visits=[
            VisitTaskRead(
                task_id=visit.task_id,
                position=visit.position,
                name=visit.name,
                location=LocationInput(
                    name=visit.location_name,
                    address=visit.location_address,
                    city=visit.location_city,
                    longitude=visit.longitude,
                    latitude=visit.latitude,
                ),
                window_start=_as_utc(visit.window_start),
                window_end=_as_utc(visit.window_end),
                duration_minutes=visit.duration_minutes,
                priority=VisitPriority(visit.priority),
                locked=visit.locked,
                completed=visit.completed,
                notes=visit.notes,
            )
            for visit in mission.visits
        ],
        expense_policy=ExpensePolicyRead(
            snapshot_id=policy.snapshot_id,
            policy_id=policy.policy_id,
            policy_version=policy.policy_version,
            allowed_rail_classes=policy.allowed_rail_classes,
            allowed_flight_classes=policy.allowed_flight_classes,
            hotel_nightly_cap_yuan=policy.hotel_nightly_cap_yuan,
            meal_daily_cap_yuan=policy.meal_daily_cap_yuan,
            local_transport_daily_cap_yuan=policy.local_transport_daily_cap_yuan,
            trip_total_cap_yuan=policy.trip_total_cap_yuan,
        ),
        transport_preferences=TransportPreferences.model_validate(
            mission.transport_preferences
        ),
        notes=mission.notes,
        created_at=_as_utc(mission.created_at),
        updated_at=_as_utc(mission.updated_at),
    )


def _to_event_read(
    event: ReplanEventRecord,
    *,
    idempotent_replay: bool,
) -> ReplanEventRead:
    return ReplanEventRead(
        event_id=event.event_id,
        mission_id=event.mission_id,
        event_type=event.event_type,
        based_on_revision=event.based_on_revision,
        accepted=True,
        idempotent_replay=idempotent_replay,
        created_at=_as_utc(event.created_at),
    )
