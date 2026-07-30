from __future__ import annotations

import hashlib
import json
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.interpreter import FieldPilotMissionInterpreter, PROMPT_VERSION, is_ready
from app.config import settings
from app.db.models import AgentRunRecord
from app.domain import AgentTraceRead, InterpretationStatus, InterpretMissionRequest, InterpretMissionResponse


class AgentRunNotFoundError(LookupError):
    pass


class AgentRequestConflictError(RuntimeError):
    pass


def _fingerprint(command: InterpretMissionRequest) -> str:
    value = json.dumps(command.model_dump(mode="json"), ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


async def interpret_mission(session: AsyncSession, command: InterpretMissionRequest) -> InterpretMissionResponse:
    fingerprint = _fingerprint(command)
    result = await session.execute(select(AgentRunRecord).where(AgentRunRecord.request_id == command.request_id))
    existing = result.scalar_one_or_none()
    if existing is not None:
        if existing.input_fingerprint != fingerprint:
            raise AgentRequestConflictError("相同 request_id 对应不同输入")
        return _response(existing, replay=True)

    run = await FieldPilotMissionInterpreter(settings).interpret(command)
    ready = is_ready(run.output)
    trace_id = f"agent-{uuid4().hex[:20]}"
    response = InterpretMissionResponse(
        status=InterpretationStatus.READY if ready else InterpretationStatus.NEEDS_CLARIFICATION,
        ready_for_submission=ready,
        draft=run.output.draft,
        clarifications=run.output.clarifications,
        safety_flags=run.output.safety_flags,
        confidence=run.output.confidence,
        trace=AgentTraceRead(
            trace_id=trace_id, mode=run.mode, model=run.model, prompt_version=PROMPT_VERSION,
            latency_ms=run.latency_ms, request_count=run.request_count,
            input_tokens=run.input_tokens, output_tokens=run.output_tokens,
            failure_type=run.failure_type,
        ),
    )
    record = AgentRunRecord(
        trace_id=trace_id, request_id=command.request_id, capability="interpret_mission",
        input_fingerprint=fingerprint, reference_date=command.reference_date, timezone=command.timezone,
        mode=run.mode.value, model=run.model, prompt_version=PROMPT_VERSION, status=response.status.value,
        output_payload=response.model_dump(mode="json"),
        usage_payload={"request_count": run.request_count, "input_tokens": run.input_tokens,
                       "output_tokens": run.output_tokens, "tool_calls": 0},
        latency_ms=run.latency_ms, failure_type=run.failure_type,
    )
    session.add(record)
    try:
        await session.commit()
    except IntegrityError:
        await session.rollback()
        replay_result = await session.execute(select(AgentRunRecord).where(AgentRunRecord.request_id == command.request_id))
        replay = replay_result.scalar_one_or_none()
        if replay is None or replay.input_fingerprint != fingerprint:
            raise AgentRequestConflictError("Agent 请求并发写入冲突") from None
        return _response(replay, replay=True)
    return response


async def get_agent_run(session: AsyncSession, trace_id: str) -> InterpretMissionResponse:
    record = await session.get(AgentRunRecord, trace_id)
    if record is None:
        raise AgentRunNotFoundError(trace_id)
    return _response(record)


def _response(record: AgentRunRecord, replay: bool = False) -> InterpretMissionResponse:
    response = InterpretMissionResponse.model_validate(record.output_payload)
    if replay:
        response.trace.idempotent_replay = True
    return response


__all__ = ["AgentRequestConflictError", "AgentRunNotFoundError", "get_agent_run", "interpret_mission"]
