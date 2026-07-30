from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db_session
from app.domain import InterpretMissionRequest, InterpretMissionResponse
from app.services.agent_service import (
    AgentRequestConflictError,
    AgentRunNotFoundError,
    get_agent_run,
    interpret_mission as interpret_mission_service,
)

router = APIRouter(prefix="/v1/agent", tags=["agent"])


@router.post(
    "/interpret-mission",
    response_model=InterpretMissionResponse,
    status_code=status.HTTP_200_OK,
)
async def interpret_mission(
    command: InterpretMissionRequest,
    session: AsyncSession = Depends(get_db_session),
) -> InterpretMissionResponse:
    try:
        return await interpret_mission_service(session, command)
    except AgentRequestConflictError as exc:
        raise HTTPException(
            status_code=409,
            detail={"code": "agent_request_conflict", "message": str(exc)},
        ) from exc


@router.get("/runs/{trace_id}", response_model=InterpretMissionResponse)
async def read_agent_run(
    trace_id: str,
    session: AsyncSession = Depends(get_db_session),
) -> InterpretMissionResponse:
    try:
        return await get_agent_run(session, trace_id)
    except AgentRunNotFoundError as exc:
        raise HTTPException(
            status_code=404,
            detail={"code": "agent_run_not_found", "trace_id": trace_id},
        ) from exc
