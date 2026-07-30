from __future__ import annotations

from uuid import uuid4

from fastapi import APIRouter, status

from app.agent.interpreter import FieldPilotMissionInterpreter, PROMPT_VERSION, is_ready
from app.config import settings
from app.domain import (
    AgentTraceRead,
    InterpretationStatus,
    InterpretMissionRequest,
    InterpretMissionResponse,
)

router = APIRouter(prefix="/v1/agent", tags=["agent"])


@router.post(
    "/interpret-mission",
    response_model=InterpretMissionResponse,
    status_code=status.HTTP_200_OK,
)
async def interpret_mission(command: InterpretMissionRequest) -> InterpretMissionResponse:
    run = await FieldPilotMissionInterpreter(settings).interpret(command)
    ready = is_ready(run.output)
    return InterpretMissionResponse(
        status=(
            InterpretationStatus.READY
            if ready
            else InterpretationStatus.NEEDS_CLARIFICATION
        ),
        ready_for_submission=ready,
        draft=run.output.draft,
        clarifications=run.output.clarifications,
        safety_flags=run.output.safety_flags,
        confidence=run.output.confidence,
        trace=AgentTraceRead(
            trace_id=f"agent-{uuid4().hex[:20]}",
            mode=run.mode,
            model=run.model,
            prompt_version=PROMPT_VERSION,
            latency_ms=run.latency_ms,
            request_count=run.request_count,
            input_tokens=run.input_tokens,
            output_tokens=run.output_tokens,
            failure_type=run.failure_type,
        ),
    )
