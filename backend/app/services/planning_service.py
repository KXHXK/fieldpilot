from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import uuid4

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import MissionRecord, PlanRevisionRecord, ProviderSnapshotRecord
from app.config import settings
from app.domain import (
    ActivateRevisionRequest,
    MissionStatus,
    PlanBundle,
    PlanGenerationRequest,
    PlanRevisionRead,
    RevisionActivationRead,
    RevisionStatus,
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
        return _to_revision_read(existing, idempotent_replay=True)

    mission_record = await session.get(MissionRecord, mission_id)
    if mission_record is None:
        raise MissionNotFoundError(mission_id)
    if command.based_on_revision != mission_record.active_revision:
        raise RevisionConflictError(
            command.based_on_revision, mission_record.active_revision
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
        input_event_id=None,
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
        status=RevisionStatus(revision.status),
        bundle=PlanBundle.model_validate(revision.plan_payload),
        idempotent_replay=idempotent_replay,
        created_at=_as_utc(revision.created_at),
    )


__all__ = [
    "NoFeasiblePlanError",
    "PlanRequestConflictError",
    "PlanRevisionNotFoundError",
    "PlanVerificationError",
    "activate_plan_revision",
    "generate_plan_revision",
    "get_plan_revision",
    "list_plan_revisions",
]
