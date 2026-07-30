from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4
from zoneinfo import ZoneInfo

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
    EventApplicationStatus,
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
from app.domain.mission import (
    BudgetChangedPayload,
    PreferenceChangedPayload,
    ReplanEventType,
    TaskAddedPayload,
    TaskCancelledPayload,
    TaskExtendedPayload,
    TaskRescheduledPayload,
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


class EventApplicationError(RuntimeError):
    def __init__(self, code: str, message: str) -> None:
        self.code = code
        super().__init__(message)


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
    mission_result = await session.execute(_mission_query(mission_id))
    mission = mission_result.scalar_one_or_none()
    if mission is None:
        raise MissionNotFoundError(mission_id)

    existing = await session.get(ReplanEventRecord, command.event_id)
    if existing is not None:
        if not _same_event(existing, mission_id, command):
            raise EventConflictError("event_id 已存在，但事件内容不一致")
        return _to_event_read(existing, idempotent_replay=True)

    if command.based_on_revision != mission.active_revision:
        raise RevisionConflictError(command.based_on_revision, mission.active_revision)

    application_status, changed_fields = await _apply_event(
        session, mission, command
    )
    applied_at = (
        datetime.now(timezone.utc)
        if application_status == EventApplicationStatus.APPLIED
        else None
    )
    event = ReplanEventRecord(
        event_id=command.event_id,
        mission_id=mission_id,
        event_type=command.event_type.value,
        based_on_revision=command.based_on_revision,
        event_payload=command.payload,
        application_status=application_status.value,
        changed_fields=changed_fields,
        applied_at=applied_at,
    )
    if mission.active_revision is not None:
        mission.status = MissionStatus.REPLAN_PENDING.value
    session.add(event)
    try:
        await session.commit()
    except IntegrityError:
        await session.rollback()
        existing = await session.get(ReplanEventRecord, command.event_id)
        if existing is None:
            raise EventApplicationError(
                "event_persistence_failed", "事件应用未能提交"
            ) from None
        if not _same_event(existing, mission_id, command):
            raise EventConflictError("event_id 并发冲突") from None
        return _to_event_read(existing, idempotent_replay=True)
    await session.refresh(event)
    return _to_event_read(event, idempotent_replay=False)


def _same_event(
    existing: ReplanEventRecord,
    mission_id: str,
    command: ReplanEventCreate,
) -> bool:
    return (
        existing.mission_id == mission_id
        and existing.event_type == command.event_type.value
        and existing.based_on_revision == command.based_on_revision
        and existing.event_payload == command.payload
    )


def _find_visit(mission: MissionRecord, task_id: str) -> VisitTaskRecord:
    visit = next((item for item in mission.visits if item.task_id == task_id), None)
    if visit is None:
        raise EventApplicationError("task_not_found", f"任务 {task_id} 不存在")
    return visit


def _ensure_visit_mutable(visit: VisitTaskRecord) -> None:
    if visit.completed or visit.locked:
        raise EventApplicationError(
            "task_immutable", f"任务 {visit.task_id} 已完成或已锁定，不能变更"
        )


def _ensure_date_in_mission(mission: MissionRecord, value: datetime) -> None:
    local_date = value.astimezone(ZoneInfo(mission.timezone)).date()
    if not mission.start_date <= local_date <= mission.end_date:
        raise EventApplicationError(
            "task_outside_mission_period", "变更后的任务不在出差日期范围内"
        )


def _change(path: str, before: object, after: object) -> dict[str, object]:
    def serializable(value: object) -> object:
        return value.isoformat() if isinstance(value, datetime) else value

    return {
        "path": path,
        "before": serializable(before),
        "after": serializable(after),
    }


async def _apply_event(
    session: AsyncSession,
    mission: MissionRecord,
    command: ReplanEventCreate,
) -> tuple[EventApplicationStatus, list[dict[str, object]]]:
    event_type = command.event_type
    changes: list[dict[str, object]] = []

    if event_type == ReplanEventType.TASK_RESCHEDULED:
        payload = TaskRescheduledPayload.model_validate(command.payload)
        visit = _find_visit(mission, payload.task_id)
        _ensure_visit_mutable(visit)
        _ensure_date_in_mission(mission, payload.new_window_start)
        _ensure_date_in_mission(mission, payload.new_window_end)
        available = int(
            (payload.new_window_end - payload.new_window_start).total_seconds() // 60
        )
        if visit.duration_minutes > available:
            raise EventApplicationError(
                "window_too_short", "新时间窗口短于任务持续时间"
            )
        before_start, before_end = visit.window_start, visit.window_end
        visit.window_start = _as_utc(payload.new_window_start)
        visit.window_end = _as_utc(payload.new_window_end)
        changes.extend(
            [
                _change(
                    f"visits.{visit.task_id}.window_start",
                    before_start,
                    visit.window_start,
                ),
                _change(
                    f"visits.{visit.task_id}.window_end",
                    before_end,
                    visit.window_end,
                ),
            ]
        )
    elif event_type == ReplanEventType.TASK_EXTENDED:
        payload = TaskExtendedPayload.model_validate(command.payload)
        visit = _find_visit(mission, payload.task_id)
        _ensure_visit_mutable(visit)
        available = int((visit.window_end - visit.window_start).total_seconds() // 60)
        if payload.new_duration_minutes > available:
            raise EventApplicationError(
                "duration_exceeds_window", "新持续时间超过任务时间窗口"
            )
        before = visit.duration_minutes
        visit.duration_minutes = payload.new_duration_minutes
        changes.append(
            _change(
                f"visits.{visit.task_id}.duration_minutes",
                before,
                visit.duration_minutes,
            )
        )
    elif event_type == ReplanEventType.TASK_CANCELLED:
        payload = TaskCancelledPayload.model_validate(command.payload)
        visit = _find_visit(mission, payload.task_id)
        _ensure_visit_mutable(visit)
        if len(mission.visits) <= 1:
            raise EventApplicationError(
                "last_task_cannot_be_cancelled", "行程至少需要保留一个工作任务"
            )
        removed_position = visit.position
        await session.delete(visit)
        await session.flush()
        remaining = sorted(
            (item for item in mission.visits if item.task_id != visit.task_id),
            key=lambda item: item.position,
        )
        for item in remaining:
            item.position += 100
        await session.flush()
        for position, item in enumerate(remaining, start=1):
            item.position = position
        changes.append(
            _change(f"visits.{visit.task_id}", {"position": removed_position}, None)
        )
    elif event_type == ReplanEventType.TASK_ADDED:
        payload = TaskAddedPayload.model_validate(command.payload)
        if len(mission.visits) >= 6:
            raise EventApplicationError("task_limit_reached", "单次行程最多 6 个任务")
        _ensure_date_in_mission(mission, payload.visit.window_start)
        _ensure_date_in_mission(mission, payload.visit.window_end)
        visit = payload.visit
        record = VisitTaskRecord(
            task_id=_new_id("tsk"),
            mission_id=mission.mission_id,
            position=len(mission.visits) + 1,
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
        mission.visits.append(record)
        changes.append(
            _change(f"visits.{record.task_id}", None, {"position": record.position})
        )
    elif event_type == ReplanEventType.BUDGET_CHANGED:
        payload = BudgetChangedPayload.model_validate(command.payload)
        policy = mission.expense_policy
        for field, after in payload.model_dump().items():
            if after is None:
                continue
            before = getattr(policy, field)
            setattr(policy, field, after)
            changes.append(_change(f"expense_policy.{field}", before, after))
    elif event_type == ReplanEventType.PREFERENCE_CHANGED:
        payload = PreferenceChangedPayload.model_validate(command.payload)
        before = mission.transport_preferences
        after = payload.transport_preferences.model_dump(mode="json")
        mission.transport_preferences = after
        changes.append(_change("transport_preferences", before, after))
    else:
        return EventApplicationStatus.RECORDED_ONLY, []

    return EventApplicationStatus.APPLIED, changes


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
        application_status=EventApplicationStatus(event.application_status),
        changed_fields=event.changed_fields or [],
        requires_replan=True,
        applied_at=_as_utc(event.applied_at) if event.applied_at else None,
        created_at=_as_utc(event.created_at),
    )
