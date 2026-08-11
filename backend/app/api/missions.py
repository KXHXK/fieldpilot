from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db_session
from app.domain import (
    ActivateRevisionRequest,
    ExecutionCheckpointCommand,
    ExecutionCheckpointRead,
    ExpensePolicyRead,
    MissionCreate,
    MissionRead,
    PlanGenerationRequest,
    PlanRevisionRead,
    ReplanEventCreate,
    ReplanEventRead,
    RevisionActivationRead,
    RevisionDiffRead,
)
from app.services.execution_service import (
    ExecutionCommandConflictError,
    ExecutionTransitionError,
    ExecutionVersionConflictError,
    advance_execution_checkpoint,
    get_execution_checkpoint,
)
from app.services.mission_service import (
    EventApplicationError,
    EventConflictError,
    MissionNotFoundError,
    RevisionConflictError,
    create_mission,
    get_mission,
    list_expense_policy_versions,
    record_replan_event,
)
from app.services.planning_service import (
    InputEventError,
    NoFeasiblePlanError,
    PlanRequestConflictError,
    PlanRevisionNotFoundError,
    PlanVerificationError,
    activate_plan_revision,
    diff_plan_revisions,
    generate_plan_revision,
    get_plan_revision,
    list_plan_revisions,
)

router = APIRouter(prefix="/v1/missions", tags=["missions-v1"])


@router.post("", response_model=MissionRead, status_code=status.HTTP_201_CREATED)
async def create_mission_endpoint(
    command: MissionCreate,
    session: AsyncSession = Depends(get_db_session),
) -> MissionRead:
    return await create_mission(session, command)


@router.get("/{mission_id}", response_model=MissionRead)
async def get_mission_endpoint(
    mission_id: str,
    session: AsyncSession = Depends(get_db_session),
) -> MissionRead:
    try:
        return await get_mission(session, mission_id)
    except MissionNotFoundError as exc:
        raise HTTPException(status_code=404, detail="任务不存在") from exc


@router.get(
    "/{mission_id}/expense-policy/versions",
    response_model=list[ExpensePolicyRead],
)
async def list_expense_policy_versions_endpoint(
    mission_id: str,
    session: AsyncSession = Depends(get_db_session),
) -> list[ExpensePolicyRead]:
    try:
        return await list_expense_policy_versions(session, mission_id)
    except MissionNotFoundError as exc:
        raise HTTPException(status_code=404, detail="任务不存在") from exc


@router.get(
    "/{mission_id}/execution",
    response_model=ExecutionCheckpointRead,
)
async def get_execution_checkpoint_endpoint(
    mission_id: str,
    session: AsyncSession = Depends(get_db_session),
) -> ExecutionCheckpointRead:
    try:
        return await get_execution_checkpoint(session, mission_id)
    except MissionNotFoundError as exc:
        raise HTTPException(status_code=404, detail="任务不存在") from exc


@router.post(
    "/{mission_id}/execution/checkpoints",
    response_model=ExecutionCheckpointRead,
)
async def advance_execution_checkpoint_endpoint(
    mission_id: str,
    command: ExecutionCheckpointCommand,
    session: AsyncSession = Depends(get_db_session),
) -> ExecutionCheckpointRead:
    try:
        return await advance_execution_checkpoint(session, mission_id, command)
    except MissionNotFoundError as exc:
        raise HTTPException(status_code=404, detail="任务不存在") from exc
    except RevisionConflictError as exc:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "revision_conflict",
                "expected_revision": exc.expected,
                "active_revision": exc.actual,
            },
        ) from exc
    except ExecutionVersionConflictError as exc:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "execution_version_conflict",
                "expected_version": exc.expected,
                "actual_version": exc.actual,
            },
        ) from exc
    except ExecutionCommandConflictError as exc:
        raise HTTPException(
            status_code=409,
            detail={"code": "execution_command_conflict", "message": str(exc)},
        ) from exc
    except ExecutionTransitionError as exc:
        raise HTTPException(
            status_code=422,
            detail={"code": exc.code, "message": str(exc)},
        ) from exc


@router.post("/{mission_id}/events", response_model=ReplanEventRead)
async def create_replan_event_endpoint(
    mission_id: str,
    command: ReplanEventCreate,
    session: AsyncSession = Depends(get_db_session),
) -> ReplanEventRead:
    try:
        return await record_replan_event(session, mission_id, command)
    except MissionNotFoundError as exc:
        raise HTTPException(status_code=404, detail="任务不存在") from exc
    except RevisionConflictError as exc:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "revision_conflict",
                "expected_revision": exc.expected,
                "active_revision": exc.actual,
            },
        ) from exc
    except EventConflictError as exc:
        raise HTTPException(
            status_code=409,
            detail={"code": "event_id_conflict", "message": str(exc)},
        ) from exc
    except EventApplicationError as exc:
        raise HTTPException(
            status_code=422,
            detail={"code": exc.code, "message": str(exc)},
        ) from exc


@router.post(
    "/{mission_id}/plans",
    response_model=PlanRevisionRead,
    status_code=status.HTTP_201_CREATED,
)
async def generate_plan_endpoint(
    mission_id: str,
    command: PlanGenerationRequest,
    session: AsyncSession = Depends(get_db_session),
) -> PlanRevisionRead:
    try:
        return await generate_plan_revision(session, mission_id, command)
    except MissionNotFoundError as exc:
        raise HTTPException(status_code=404, detail="任务不存在") from exc
    except RevisionConflictError as exc:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "revision_conflict",
                "expected_revision": exc.expected,
                "active_revision": exc.actual,
            },
        ) from exc
    except NoFeasiblePlanError as exc:
        raise HTTPException(
            status_code=422,
            detail={"code": "no_feasible_plan", "reasons": exc.reasons},
        ) from exc
    except PlanVerificationError as exc:
        raise HTTPException(
            status_code=500,
            detail={"code": "plan_verification_failed", "violations": exc.violations},
        ) from exc
    except PlanRequestConflictError as exc:
        raise HTTPException(
            status_code=409,
            detail={"code": "plan_request_conflict", "message": str(exc)},
        ) from exc
    except InputEventError as exc:
        raise HTTPException(
            status_code=422,
            detail={"code": exc.code, "message": str(exc)},
        ) from exc


@router.get("/{mission_id}/revisions", response_model=list[PlanRevisionRead])
async def list_revisions_endpoint(
    mission_id: str,
    session: AsyncSession = Depends(get_db_session),
) -> list[PlanRevisionRead]:
    try:
        return await list_plan_revisions(session, mission_id)
    except MissionNotFoundError as exc:
        raise HTTPException(status_code=404, detail="任务不存在") from exc


@router.get(
    "/{mission_id}/revisions/{from_revision}/diff/{to_revision}",
    response_model=RevisionDiffRead,
)
async def diff_revisions_endpoint(
    mission_id: str,
    from_revision: int,
    to_revision: int,
    session: AsyncSession = Depends(get_db_session),
) -> RevisionDiffRead:
    try:
        return await diff_plan_revisions(
            session, mission_id, from_revision, to_revision
        )
    except MissionNotFoundError as exc:
        raise HTTPException(status_code=404, detail="任务不存在") from exc
    except PlanRevisionNotFoundError as exc:
        raise HTTPException(status_code=404, detail="计划修订不存在") from exc


@router.get(
    "/{mission_id}/revisions/{revision_number}",
    response_model=PlanRevisionRead,
)
async def get_revision_endpoint(
    mission_id: str,
    revision_number: int,
    session: AsyncSession = Depends(get_db_session),
) -> PlanRevisionRead:
    try:
        return await get_plan_revision(session, mission_id, revision_number)
    except PlanRevisionNotFoundError as exc:
        raise HTTPException(status_code=404, detail="计划修订不存在") from exc


@router.post(
    "/{mission_id}/revisions/{revision_number}/activate",
    response_model=RevisionActivationRead,
)
async def activate_revision_endpoint(
    mission_id: str,
    revision_number: int,
    command: ActivateRevisionRequest,
    session: AsyncSession = Depends(get_db_session),
) -> RevisionActivationRead:
    try:
        return await activate_plan_revision(
            session, mission_id, revision_number, command
        )
    except MissionNotFoundError as exc:
        raise HTTPException(status_code=404, detail="任务不存在") from exc
    except PlanRevisionNotFoundError as exc:
        raise HTTPException(status_code=404, detail="计划修订不存在") from exc
    except RevisionConflictError as exc:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "revision_conflict",
                "expected_revision": exc.expected,
                "active_revision": exc.actual,
            },
        ) from exc
    except PlanRequestConflictError as exc:
        raise HTTPException(
            status_code=409,
            detail={"code": "plan_request_conflict", "message": str(exc)},
        ) from exc
