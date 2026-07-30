from __future__ import annotations

from datetime import date, datetime
from enum import StrEnum
from typing import Literal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import Field, field_validator, model_validator

from app.domain.mission import StrictModel, Urgency


class AgentMode(StrEnum):
    MOCK = "mock"
    LIVE = "live"
    FALLBACK = "fallback"


class InterpretationStatus(StrEnum):
    READY = "ready"
    NEEDS_CLARIFICATION = "needs_clarification"


class LocationDraft(StrictModel):
    name: str | None = Field(default=None, max_length=120)
    address: str | None = Field(default=None, max_length=240)
    city: str | None = Field(default=None, max_length=40)


class VisitDraft(StrictModel):
    name: str | None = Field(default=None, max_length=120)
    address: str | None = Field(default=None, max_length=240)
    city: str | None = Field(default=None, max_length=40)
    window_start: datetime | None = None
    window_end: datetime | None = None
    duration_minutes: int | None = Field(default=None, ge=15, le=720)
    priority: str = Field(default="normal", max_length=20)
    notes: str = Field(default="", max_length=500)

    @model_validator(mode="after")
    def validate_window(self) -> VisitDraft:
        if self.window_start is not None and self.window_start.tzinfo is None:
            raise ValueError("任务开始时间必须包含时区")
        if self.window_end is not None and self.window_end.tzinfo is None:
            raise ValueError("任务结束时间必须包含时区")
        if (
            self.window_start is not None
            and self.window_end is not None
            and self.window_end <= self.window_start
        ):
            raise ValueError("任务结束时间必须晚于开始时间")
        return self


class ExpensePolicyDraft(StrictModel):
    policy_id: str = Field(default="agent-draft", max_length=80)
    policy_version: str = Field(default="draft", max_length=40)
    allowed_rail_classes: list[str] | None = Field(default=None, max_length=5)
    allowed_flight_classes: list[str] | None = Field(default=None, max_length=5)
    hotel_nightly_cap_yuan: int | None = Field(default=None, gt=0, le=10_000)
    meal_daily_cap_yuan: int | None = Field(default=None, gt=0, le=5_000)
    local_transport_daily_cap_yuan: int | None = Field(default=None, gt=0, le=5_000)
    trip_total_cap_yuan: int | None = Field(default=None, gt=0, le=1_000_000)


class MissionDraft(StrictModel):
    origin: LocationDraft = Field(default_factory=LocationDraft)
    destination_city: str | None = Field(default=None, max_length=40)
    start_date: date | None = None
    end_date: date | None = None
    timezone: str = Field(default="Asia/Shanghai", max_length=64)
    urgency: Urgency = Urgency.BALANCED
    visits: list[VisitDraft] = Field(default_factory=list, max_length=6)
    expense_policy: ExpensePolicyDraft = Field(default_factory=ExpensePolicyDraft)
    preferred_intercity_modes: list[str] = Field(default_factory=lambda: ["rail"])
    preferred_local_modes: list[str] = Field(
        default_factory=lambda: ["transit", "taxi", "walking"]
    )
    notes: str = Field(default="", max_length=1000)

    @field_validator("timezone")
    @classmethod
    def validate_timezone(cls, value: str) -> str:
        try:
            ZoneInfo(value)
        except ZoneInfoNotFoundError as exc:
            raise ValueError("未知时区") from exc
        return value

    @model_validator(mode="after")
    def validate_dates(self) -> MissionDraft:
        if self.start_date and self.end_date and self.end_date < self.start_date:
            raise ValueError("结束日期不能早于开始日期")
        return self


class ClarificationQuestion(StrictModel):
    field: str = Field(min_length=1, max_length=80)
    question: str = Field(min_length=1, max_length=200)
    reason: str = Field(min_length=1, max_length=240)


class AgentMissionOutput(StrictModel):
    draft: MissionDraft
    clarifications: list[ClarificationQuestion] = Field(default_factory=list, max_length=3)
    confidence: float = Field(ge=0, le=1)
    safety_flags: list[str] = Field(default_factory=list, max_length=5)


class InterpretMissionRequest(StrictModel):
    request_id: str = Field(min_length=8, max_length=120)
    text: str = Field(min_length=10, max_length=4000)
    reference_date: date
    timezone: str = Field(default="Asia/Shanghai", max_length=64)

    @field_validator("timezone")
    @classmethod
    def validate_timezone(cls, value: str) -> str:
        try:
            ZoneInfo(value)
        except ZoneInfoNotFoundError as exc:
            raise ValueError("未知时区") from exc
        return value


class AgentTraceRead(StrictModel):
    trace_id: str
    mode: AgentMode
    model: str
    prompt_version: str
    latency_ms: float = Field(ge=0)
    request_count: int = Field(ge=0)
    input_tokens: int | None = Field(default=None, ge=0)
    output_tokens: int | None = Field(default=None, ge=0)
    tool_calls: Literal[0] = 0
    failure_type: str | None = None
    idempotent_replay: bool = False


class InterpretMissionResponse(StrictModel):
    status: InterpretationStatus
    ready_for_submission: bool
    draft: MissionDraft
    clarifications: list[ClarificationQuestion]
    safety_flags: list[str]
    confidence: float
    trace: AgentTraceRead


__all__ = [
    "AgentMissionOutput",
    "AgentMode",
    "AgentTraceRead",
    "ClarificationQuestion",
    "ExpensePolicyDraft",
    "InterpretMissionRequest",
    "InterpretMissionResponse",
    "InterpretationStatus",
    "LocationDraft",
    "MissionDraft",
    "VisitDraft",
]
