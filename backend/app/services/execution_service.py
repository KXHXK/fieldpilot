from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.exc import StaleDataError

from app.db.models import (
    ExecutionCheckpointRecord,
    ExecutionCommandRecord,
    MissionRecord,
    PlanRevisionRecord,
    VisitTaskRecord,
)
from app.domain import (
    ExecutionAction,
    ExecutionCheckpointCommand,
    ExecutionCheckpointRead,
    MissionStatus,
    PlanBundle,
    PlanSegment,
    SegmentType,
)
from app.services.mission_service import MissionNotFoundError, RevisionConflictError


class ExecutionCommandConflictError(RuntimeError):
    pass


class ExecutionVersionConflictError(RuntimeError):
    def __init__(self, expected: int, actual: int) -> None:
        self.expected = expected
        self.actual = actual
        super().__init__(
            f"执行检查点版本冲突：请求基于 {expected}，当前版本为 {actual}"
        )


class ExecutionTransitionError(RuntimeError):
    def __init__(self, code: str, message: str) -> None:
        self.code = code
        super().__init__(message)


_CHECKPOINT_SEGMENT_TYPES = {
    SegmentType.INTERCITY_TRANSPORT,
    SegmentType.LOCAL_TRANSPORT,
    SegmentType.VISIT,
}


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _preferred_segments(revision: PlanRevisionRecord) -> list[PlanSegment]:
    bundle = PlanBundle.model_validate(revision.plan_payload)
    option = next(
        item
        for item in bundle.options
        if item.option_id == bundle.preferred_option_id
    )
    return sorted(
        option.segments,
        key=lambda item: (item.start_at, item.end_at, item.segment_id),
    )


def _same_command(
    existing: ExecutionCommandRecord,
    mission_id: str,
    command: ExecutionCheckpointCommand,
) -> bool:
    return (
        existing.mission_id == mission_id
        and existing.based_on_revision == command.based_on_revision
        and existing.expected_version == command.expected_version
        and existing.action == command.action.value
        and existing.through_segment_id == command.through_segment_id
    )


def _checkpoint_read(
    mission_id: str,
    checkpoint: ExecutionCheckpointRecord | None,
    *,
    idempotent_replay: bool = False,
) -> ExecutionCheckpointRead:
    if checkpoint is None:
        return ExecutionCheckpointRead(mission_id=mission_id, version=0)
    protected = [
        PlanSegment.model_validate(item) for item in checkpoint.protected_segments
    ]
    return ExecutionCheckpointRead(
        mission_id=mission_id,
        version=checkpoint.version,
        source_revision=checkpoint.source_revision,
        locked_through_segment_id=checkpoint.locked_through_segment_id,
        locked_through_at=(
            _as_utc(checkpoint.locked_through_at)
            if checkpoint.locked_through_at
            else None
        ),
        completed_through_segment_id=checkpoint.completed_through_segment_id,
        completed_through_at=(
            _as_utc(checkpoint.completed_through_at)
            if checkpoint.completed_through_at
            else None
        ),
        protected_segment_ids=[item.segment_id for item in protected],
        idempotent_replay=idempotent_replay,
        updated_at=_as_utc(checkpoint.updated_at),
    )


async def get_execution_checkpoint(
    session: AsyncSession,
    mission_id: str,
) -> ExecutionCheckpointRead:
    if await session.get(MissionRecord, mission_id) is None:
        raise MissionNotFoundError(mission_id)
    checkpoint = await session.get(ExecutionCheckpointRecord, mission_id)
    return _checkpoint_read(mission_id, checkpoint)


async def advance_execution_checkpoint(
    session: AsyncSession,
    mission_id: str,
    command: ExecutionCheckpointCommand,
) -> ExecutionCheckpointRead:
    existing_command = await session.get(ExecutionCommandRecord, command.command_id)
    if existing_command is not None:
        if not _same_command(existing_command, mission_id, command):
            raise ExecutionCommandConflictError(
                "command_id 已存在，但执行命令内容不一致"
            )
        return ExecutionCheckpointRead.model_validate(
            {**existing_command.result_payload, "idempotent_replay": True}
        )

    mission = await session.get(MissionRecord, mission_id)
    if mission is None:
        raise MissionNotFoundError(mission_id)
    if mission.active_revision != command.based_on_revision:
        raise RevisionConflictError(command.based_on_revision, mission.active_revision)

    checkpoint = await session.get(ExecutionCheckpointRecord, mission_id)
    current_version = checkpoint.version if checkpoint is not None else 0
    if command.expected_version != current_version:
        raise ExecutionVersionConflictError(command.expected_version, current_version)

    revision_result = await session.execute(
        select(PlanRevisionRecord).where(
            PlanRevisionRecord.mission_id == mission_id,
            PlanRevisionRecord.revision == command.based_on_revision,
        )
    )
    revision = revision_result.scalar_one_or_none()
    if revision is None:
        raise ExecutionTransitionError(
            "active_revision_missing", "当前激活修订不存在"
        )
    segments = _preferred_segments(revision)
    target = next(
        (item for item in segments if item.segment_id == command.through_segment_id),
        None,
    )
    if target is None:
        raise ExecutionTransitionError(
            "segment_not_in_active_plan", "目标行程段不属于当前激活方案"
        )
    if target.segment_type not in _CHECKPOINT_SEGMENT_TYPES:
        raise ExecutionTransitionError(
            "segment_not_checkpointable", "只能在交通或工作任务段推进执行位置"
        )
    target_end = _as_utc(target.end_at)

    if checkpoint is None:
        checkpoint = ExecutionCheckpointRecord(
            mission_id=mission_id,
            version=0,
            source_revision=command.based_on_revision,
            protected_segments=[],
        )
        session.add(checkpoint)

    if command.action == ExecutionAction.LOCK_THROUGH:
        current_locked = (
            _as_utc(checkpoint.locked_through_at)
            if checkpoint.locked_through_at
            else None
        )
        if current_locked is not None and target_end <= current_locked:
            raise ExecutionTransitionError(
                "execution_not_advanced", "锁定位置必须晚于当前锁定位置"
            )
        protected = [
            item for item in segments if _as_utc(item.end_at) <= target_end
        ]
        if target.segment_id not in {item.segment_id for item in protected}:
            raise ExecutionTransitionError(
                "invalid_execution_prefix", "无法构造连续的受保护执行前缀"
            )
        checkpoint.source_revision = command.based_on_revision
        checkpoint.locked_through_segment_id = target.segment_id
        checkpoint.locked_through_at = target_end
        checkpoint.protected_segments = [
            item.model_dump(mode="json") for item in protected
        ]
        protected_task_ids = {
            item.task_id for item in protected if item.task_id is not None
        }
        if protected_task_ids:
            task_result = await session.execute(
                select(VisitTaskRecord).where(
                    VisitTaskRecord.mission_id == mission_id,
                    VisitTaskRecord.task_id.in_(protected_task_ids),
                )
            )
            for visit in task_result.scalars().all():
                visit.locked = True
    else:
        if checkpoint.locked_through_at is None:
            raise ExecutionTransitionError(
                "completion_exceeds_lock", "必须先锁定行程段，再推进完成位置"
            )
        locked_at = _as_utc(checkpoint.locked_through_at)
        if target_end > locked_at:
            raise ExecutionTransitionError(
                "completion_exceeds_lock", "完成位置不能超过当前锁定位置"
            )
        current_completed = (
            _as_utc(checkpoint.completed_through_at)
            if checkpoint.completed_through_at
            else None
        )
        if current_completed is not None and target_end <= current_completed:
            raise ExecutionTransitionError(
                "execution_not_advanced", "完成位置必须晚于当前完成位置"
            )
        protected_ids = {
            PlanSegment.model_validate(item).segment_id
            for item in checkpoint.protected_segments
        }
        if target.segment_id not in protected_ids:
            raise ExecutionTransitionError(
                "completion_exceeds_lock", "完成位置不在受保护前缀内"
            )
        checkpoint.completed_through_segment_id = target.segment_id
        checkpoint.completed_through_at = target_end
        completed_task_ids = {
            item.task_id
            for item in segments
            if item.task_id is not None and _as_utc(item.end_at) <= target_end
        }
        if completed_task_ids:
            task_result = await session.execute(
                select(VisitTaskRecord).where(
                    VisitTaskRecord.mission_id == mission_id,
                    VisitTaskRecord.task_id.in_(completed_task_ids),
                )
            )
            for visit in task_result.scalars().all():
                visit.locked = True
                visit.completed = True
        checkpointable = [
            item for item in segments if item.segment_type in _CHECKPOINT_SEGMENT_TYPES
        ]
        if checkpointable and target.segment_id == checkpointable[-1].segment_id:
            mission.status = MissionStatus.COMPLETED.value

    checkpoint.version = current_version + 1
    checkpoint.updated_at = datetime.now(timezone.utc)
    response = _checkpoint_read(mission_id, checkpoint)
    execution_command = ExecutionCommandRecord(
        command_id=command.command_id,
        mission_id=mission_id,
        based_on_revision=command.based_on_revision,
        expected_version=command.expected_version,
        action=command.action.value,
        through_segment_id=command.through_segment_id,
        result_payload=response.model_dump(mode="json"),
    )
    session.add(execution_command)
    try:
        await session.commit()
    except (IntegrityError, StaleDataError):
        await session.rollback()
        replay = await session.get(ExecutionCommandRecord, command.command_id)
        if replay is not None and _same_command(replay, mission_id, command):
            return ExecutionCheckpointRead.model_validate(
                {**replay.result_payload, "idempotent_replay": True}
            )
        actual = await session.get(ExecutionCheckpointRecord, mission_id)
        raise ExecutionVersionConflictError(
            command.expected_version,
            actual.version if actual is not None else 0,
        ) from None
    return response


async def get_protected_prefix(
    session: AsyncSession,
    mission_id: str,
) -> tuple[list[PlanSegment], str | None]:
    checkpoint = await session.get(ExecutionCheckpointRecord, mission_id)
    if checkpoint is None or not checkpoint.protected_segments:
        return [], None
    return (
        [PlanSegment.model_validate(item) for item in checkpoint.protected_segments],
        checkpoint.locked_through_segment_id,
    )


__all__ = [
    "ExecutionCommandConflictError",
    "ExecutionTransitionError",
    "ExecutionVersionConflictError",
    "advance_execution_checkpoint",
    "get_execution_checkpoint",
    "get_protected_prefix",
]
