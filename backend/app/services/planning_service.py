from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import uuid4

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import (
    MissionRecord,
    PlanRevisionRecord,
    ProviderSnapshotRecord,
    ReplanEventRecord,
)
from app.config import settings
from app.domain import (
    ActivateRevisionRequest,
    MissionStatus,
    PlanBundle,
    PlanGenerationRequest,
    PlanRevisionRead,
    RevisionDiffRead,
    RevisionActivationRead,
    RevisionStatus,
    SegmentChange,
)
from app.planning import (
    BoundedMissionPlanner,
    NoFeasiblePlanError,
    PlanVerificationError,
    PlanVerifier,
    PolicyEngine,
)
from app.providers import create_candidate_provider
from app.services.mission_service import (
    MissionNotFoundError,
    RevisionConflictError,
    get_mission,
)


class PlanRevisionNotFoundError(LookupError):
    pass


class PlanRequestConflictError(RuntimeError):
    pass


class InputEventError(RuntimeError):
    def __init__(self, code: str, message: str) -> None:
        self.code = code
        super().__init__(message)


def _new_id(prefix: str) -> str:
    return f"{prefix}-{uuid4().hex[:20]}"


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


async def generate_plan_revision(
    session: AsyncSession,
    mission_id: str,
    command: PlanGenerationRequest,
) -> PlanRevisionRead:
    existing_result = await session.execute(
        select(PlanRevisionRecord).where(
            PlanRevisionRecord.mission_id == mission_id,
            PlanRevisionRecord.request_id == command.request_id,
        )
    )
    existing = existing_result.scalar_one_or_none()
    if existing is not None:
        if (
            existing.based_on_revision != command.based_on_revision
            or existing.input_event_id != command.input_event_id
        ):
            raise PlanRequestConflictError(
                "request_id 已存在，但计划请求内容不一致"
            )
        return _to_revision_read(existing, idempotent_replay=True)

    mission_record = await session.get(MissionRecord, mission_id)
    if mission_record is None:
        raise MissionNotFoundError(mission_id)
    if command.based_on_revision != mission_record.active_revision:
        raise RevisionConflictError(
            command.based_on_revision, mission_record.active_revision
        )
    if command.input_event_id is not None:
        input_event = await session.get(ReplanEventRecord, command.input_event_id)
        if input_event is None or input_event.mission_id != mission_id:
            raise InputEventError("input_event_not_found", "触发事件不存在")
        if input_event.based_on_revision != command.based_on_revision:
            raise InputEventError(
                "input_event_revision_mismatch",
                "触发事件所基于的版本与计划请求不一致",
            )

    mission = await get_mission(session, mission_id)
    provider = create_candidate_provider(settings)
    policy_engine = PolicyEngine()
    planner = BoundedMissionPlanner(provider, policy_engine)
    verifier = PlanVerifier(policy_engine)
    try:
        candidates = provider.search(mission)
        options = await planner.plan(mission, candidates)
        for option in options:
            verifier.verify(mission, option)
        route_snapshots = provider.provider_snapshots()
    finally:
        await provider.aclose()

    snapshot_id = _new_id("snap")
    generated_at = datetime.now(timezone.utc)
    snapshot_records = [ProviderSnapshotRecord(
        snapshot_id=snapshot_id,
        mission_id=mission_id,
        provider=candidates.provider,
        capability="planning_candidates",
        source_mode=candidates.source_mode.value,
        query_fingerprint=candidates.query_fingerprint,
        payload=candidates.model_dump(mode="json"),
        fetched_at=candidates.fetched_at,
        expires_at=candidates.fetched_at + timedelta(hours=1),
    )]
    snapshot_ids = [snapshot_id]
    for route_snapshot in route_snapshots:
        route_snapshot_id = _new_id("snap")
        snapshot_ids.append(route_snapshot_id)
        snapshot_records.append(
            ProviderSnapshotRecord(
                snapshot_id=route_snapshot_id,
                mission_id=mission_id,
                provider=route_snapshot.provider,
                capability=route_snapshot.capability,
                source_mode=route_snapshot.source_mode.value,
                query_fingerprint=route_snapshot.query_fingerprint,
                payload=route_snapshot.payload,
                fetched_at=route_snapshot.fetched_at,
                expires_at=route_snapshot.expires_at,
            )
        )
    next_revision_result = await session.execute(
        select(func.coalesce(func.max(PlanRevisionRecord.revision), 0) + 1).where(
            PlanRevisionRecord.mission_id == mission_id
        )
    )
    revision_number = int(next_revision_result.scalar_one())
    bundle = PlanBundle(
        mission_id=mission_id,
        preferred_option_id=options[0].option_id,
        options=options,
        provider_snapshot_ids=snapshot_ids,
        generated_at=generated_at,
        planner_version=planner.version,
        verifier_version=verifier.version,
    )
    revision = PlanRevisionRecord(
        revision_id=_new_id("rev"),
        mission_id=mission_id,
        revision=revision_number,
        based_on_revision=command.based_on_revision,
        request_id=command.request_id,
        input_event_id=command.input_event_id,
        status=RevisionStatus.PROPOSED.value,
        plan_payload=bundle.model_dump(mode="json"),
    )
    session.add_all([*snapshot_records, revision])
    mission_record.status = MissionStatus.READY.value
    try:
        await session.commit()
    except IntegrityError:
        await session.rollback()
        replay_result = await session.execute(
            select(PlanRevisionRecord).where(
                PlanRevisionRecord.mission_id == mission_id,
                PlanRevisionRecord.request_id == command.request_id,
            )
        )
        replay = replay_result.scalar_one_or_none()
        if replay is None:
            raise PlanRequestConflictError("计划修订并发写入冲突") from None
        return _to_revision_read(replay, idempotent_replay=True)
    await session.refresh(revision)
    return _to_revision_read(revision, idempotent_replay=False)


async def list_plan_revisions(
    session: AsyncSession,
    mission_id: str,
) -> list[PlanRevisionRead]:
    mission = await session.get(MissionRecord, mission_id)
    if mission is None:
        raise MissionNotFoundError(mission_id)
    result = await session.execute(
        select(PlanRevisionRecord)
        .where(PlanRevisionRecord.mission_id == mission_id)
        .order_by(PlanRevisionRecord.revision)
    )
    return [_to_revision_read(item) for item in result.scalars().all()]


async def get_plan_revision(
    session: AsyncSession,
    mission_id: str,
    revision_number: int,
) -> PlanRevisionRead:
    result = await session.execute(
        select(PlanRevisionRecord).where(
            PlanRevisionRecord.mission_id == mission_id,
            PlanRevisionRecord.revision == revision_number,
        )
    )
    revision = result.scalar_one_or_none()
    if revision is None:
        raise PlanRevisionNotFoundError(revision_number)
    return _to_revision_read(revision)


async def activate_plan_revision(
    session: AsyncSession,
    mission_id: str,
    revision_number: int,
    command: ActivateRevisionRequest,
) -> RevisionActivationRead:
    mission = await session.get(MissionRecord, mission_id)
    if mission is None:
        raise MissionNotFoundError(mission_id)
    result = await session.execute(
        select(PlanRevisionRecord).where(
            PlanRevisionRecord.mission_id == mission_id,
            PlanRevisionRecord.revision == revision_number,
        )
    )
    target = result.scalar_one_or_none()
    if target is None:
        raise PlanRevisionNotFoundError(revision_number)
    if (
        mission.active_revision == revision_number
        and target.status == RevisionStatus.ACTIVE.value
    ):
        return RevisionActivationRead(
            mission_id=mission_id,
            active_revision=revision_number,
            status=RevisionStatus.ACTIVE,
            idempotent_replay=True,
        )
    if command.expected_active_revision != mission.active_revision:
        raise RevisionConflictError(
            command.expected_active_revision, mission.active_revision
        )
    if target.status != RevisionStatus.PROPOSED.value:
        raise PlanRequestConflictError(
            f"修订 {revision_number} 当前状态为 {target.status}，不能激活"
        )
    if mission.active_revision is not None:
        previous_result = await session.execute(
            select(PlanRevisionRecord).where(
                PlanRevisionRecord.mission_id == mission_id,
                PlanRevisionRecord.revision == mission.active_revision,
            )
        )
        previous = previous_result.scalar_one_or_none()
        if previous is not None:
            previous.status = RevisionStatus.SUPERSEDED.value
    target.status = RevisionStatus.ACTIVE.value
    mission.active_revision = revision_number
    mission.status = MissionStatus.ACTIVE.value
    await session.commit()
    return RevisionActivationRead(
        mission_id=mission_id,
        active_revision=revision_number,
        status=RevisionStatus.ACTIVE,
        idempotent_replay=False,
    )


def _preferred_option(revision: PlanRevisionRead):
    return next(
        option
        for option in revision.bundle.options
        if option.option_id == revision.bundle.preferred_option_id
    )


def _indexed_segments(option) -> dict[str, object]:
    indexed: dict[str, object] = {}
    counts: dict[str, int] = {}
    for segment in option.segments:
        base = (
            f"task:{segment.task_id}"
            if segment.task_id
            else f"candidate:{segment.candidate_id}"
            if segment.candidate_id
            else (
                f"{segment.segment_type.value}:{segment.title}:"
                f"{segment.from_ref or ''}:{segment.to_ref or ''}"
            )
        )
        counts[base] = counts.get(base, 0) + 1
        indexed[f"{base}#{counts[base]}"] = segment
    return indexed


async def diff_plan_revisions(
    session: AsyncSession,
    mission_id: str,
    from_revision: int,
    to_revision: int,
) -> RevisionDiffRead:
    if await session.get(MissionRecord, mission_id) is None:
        raise MissionNotFoundError(mission_id)
    before = await get_plan_revision(session, mission_id, from_revision)
    after = await get_plan_revision(session, mission_id, to_revision)
    before_option = _preferred_option(before)
    after_option = _preferred_option(after)
    before_segments = _indexed_segments(before_option)
    after_segments = _indexed_segments(after_option)
    changes: list[SegmentChange] = []
    preserved = 0
    for identity in sorted(before_segments.keys() | after_segments.keys()):
        old = before_segments.get(identity)
        new = after_segments.get(identity)
        if old is None:
            changes.append(
                SegmentChange(identity=identity, change_type="added", after=new)
            )
        elif new is None:
            changes.append(
                SegmentChange(identity=identity, change_type="removed", before=old)
            )
        elif old.model_dump(mode="json") != new.model_dump(mode="json"):
            changes.append(
                SegmentChange(
                    identity=identity,
                    change_type="changed",
                    before=old,
                    after=new,
                )
            )
        else:
            preserved += 1
    before_warnings = set(before_option.warnings)
    after_warnings = set(after_option.warnings)
    return RevisionDiffRead(
        mission_id=mission_id,
        from_revision=from_revision,
        to_revision=to_revision,
        input_event_id=after.input_event_id,
        changes=changes,
        preserved_segment_count=preserved,
        cost_delta_yuan=(
            after_option.costs.planned_total_yuan
            - before_option.costs.planned_total_yuan
        ),
        score_delta=round(after_option.score.total - before_option.score.total, 2),
        warnings_added=sorted(after_warnings - before_warnings),
        warnings_removed=sorted(before_warnings - after_warnings),
    )


def _to_revision_read(
    revision: PlanRevisionRecord,
    *,
    idempotent_replay: bool = False,
) -> PlanRevisionRead:
    return PlanRevisionRead(
        revision_id=revision.revision_id,
        mission_id=revision.mission_id,
        revision=revision.revision,
        based_on_revision=revision.based_on_revision,
        request_id=revision.request_id,
        input_event_id=revision.input_event_id,
        status=RevisionStatus(revision.status),
        bundle=PlanBundle.model_validate(revision.plan_payload),
        idempotent_replay=idempotent_replay,
        created_at=_as_utc(revision.created_at),
    )


__all__ = [
    "NoFeasiblePlanError",
    "InputEventError",
    "PlanRequestConflictError",
    "PlanRevisionNotFoundError",
    "PlanVerificationError",
    "activate_plan_revision",
    "diff_plan_revisions",
    "generate_plan_revision",
    "get_plan_revision",
    "list_plan_revisions",
]
