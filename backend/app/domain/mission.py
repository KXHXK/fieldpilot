from __future__ import annotations

from datetime import date, datetime
from enum import StrEnum
from typing import Any, Literal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Urgency(StrEnum):
    TIGHT = "tight"
    BALANCED = "balanced"
    FLEXIBLE = "flexible"


class MissionStatus(StrEnum):
    DRAFT = "draft"
    NEEDS_INPUT = "needs_input"
    PLANNING = "planning"
    READY = "ready"
    ACTIVE = "active"
    REPLAN_PENDING = "replan_pending"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class VisitPriority(StrEnum):
    REQUIRED = "required"
    HIGH = "high"
    NORMAL = "normal"
    OPTIONAL = "optional"


class ReplanEventType(StrEnum):
    TASK_RESCHEDULED = "task_rescheduled"
    TASK_CANCELLED = "task_cancelled"
    TASK_ADDED = "task_added"
    TASK_EXTENDED = "task_extended"
    BUDGET_CHANGED = "budget_changed"
    PREFERENCE_CHANGED = "preference_changed"
    TRANSPORT_DISRUPTION = "transport_disruption"
    WEATHER_RISK = "weather_risk"


class LocationInput(StrictModel):
    name: str = Field(min_length=1, max_length=120)
    address: str = Field(min_length=1, max_length=240)
    city: str = Field(min_length=1, max_length=40)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    latitude: float | None = Field(default=None, ge=-90, le=90)

    @model_validator(mode="after")
    def coordinates_are_paired(self) -> LocationInput:
        if (self.longitude is None) != (self.latitude is None):
            raise ValueError("longitude 和 latitude 必须同时提供或同时省略")
        return self


class VisitTaskCreate(StrictModel):
    name: str = Field(min_length=1, max_length=120)
    location: LocationInput
    window_start: datetime
    window_end: datetime
    duration_minutes: int = Field(ge=15, le=720)
    priority: VisitPriority = VisitPriority.NORMAL
    locked: bool = False
    notes: str = Field(default="", max_length=500)

    @model_validator(mode="after")
    def validate_window(self) -> VisitTaskCreate:
        if self.window_start.tzinfo is None or self.window_end.tzinfo is None:
            raise ValueError("任务时间必须包含时区偏移")
        if self.window_end <= self.window_start:
            raise ValueError("任务结束时间必须晚于开始时间")
        available_minutes = int(
            (self.window_end - self.window_start).total_seconds() // 60
        )
        if self.duration_minutes > available_minutes:
            raise ValueError("任务持续时间不能超过可用时间窗")
        return self


class TransportPreferences(StrictModel):
    preferred_intercity_modes: list[str] = Field(
        default_factory=lambda: ["rail", "flight"], min_length=1, max_length=3
    )
    preferred_local_modes: list[str] = Field(
        default_factory=lambda: ["transit", "taxi", "walking"],
        min_length=1,
        max_length=5,
    )
    minimum_transfer_minutes: int = Field(default=30, ge=10, le=180)
    allow_early_arrival_day: bool = False

    @field_validator("preferred_intercity_modes", "preferred_local_modes")
    @classmethod
    def normalize_modes(cls, values: list[str]) -> list[str]:
        normalized = list(dict.fromkeys(value.strip().lower() for value in values if value.strip()))
        if not normalized:
            raise ValueError("至少提供一种交通方式")
        return normalized


class ExpensePolicyInput(StrictModel):
    policy_id: str = Field(default="demo-cn-v1", min_length=1, max_length=80)
    policy_version: str = Field(default="1", min_length=1, max_length=40)
    allowed_rail_classes: list[str] = Field(
        default_factory=lambda: ["second_class"], max_length=5
    )
    allowed_flight_classes: list[str] = Field(
        default_factory=lambda: ["economy"], max_length=5
    )
    hotel_nightly_cap_yuan: int = Field(gt=0, le=10_000)
    meal_daily_cap_yuan: int = Field(gt=0, le=5_000)
    local_transport_daily_cap_yuan: int = Field(gt=0, le=5_000)
    trip_total_cap_yuan: int = Field(gt=0, le=1_000_000)

    @model_validator(mode="after")
    def at_least_one_intercity_class(self) -> ExpensePolicyInput:
        if not self.allowed_rail_classes and not self.allowed_flight_classes:
            raise ValueError("铁路和航班报销等级不能同时为空")
        return self


class MissionCreate(StrictModel):
    origin: LocationInput
    start_date: date
    end_date: date
    timezone: str = Field(default="Asia/Shanghai", min_length=1, max_length=64)
    urgency: Urgency = Urgency.BALANCED
    visits: list[VisitTaskCreate] = Field(min_length=1, max_length=6)
    expense_policy: ExpensePolicyInput
    transport_preferences: TransportPreferences = Field(default_factory=TransportPreferences)
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
    def validate_period_and_visits(self) -> MissionCreate:
        if self.end_date < self.start_date:
            raise ValueError("结束日期不能早于开始日期")
        if (self.end_date - self.start_date).days > 6:
            raise ValueError("单次任务周期最多 7 天")
        for visit in self.visits:
            local_date = visit.window_start.astimezone(ZoneInfo(self.timezone)).date()
            if not self.start_date <= local_date <= self.end_date:
                raise ValueError(f"任务“{visit.name}”不在任务日期范围内")
        return self


class VisitTaskRead(StrictModel):
    task_id: str
    position: int
    name: str
    location: LocationInput
    window_start: datetime
    window_end: datetime
    duration_minutes: int
    priority: VisitPriority
    locked: bool
    completed: bool
    notes: str


class ExpensePolicyRead(ExpensePolicyInput):
    snapshot_id: str


class MissionRead(StrictModel):
    mission_id: str
    origin: LocationInput
    start_date: date
    end_date: date
    timezone: str
    urgency: Urgency
    status: MissionStatus
    active_revision: int | None
    visits: list[VisitTaskRead]
    expense_policy: ExpensePolicyRead
    transport_preferences: TransportPreferences
    notes: str
    created_at: datetime
    updated_at: datetime


class TaskRescheduledPayload(StrictModel):
    task_id: str = Field(min_length=1, max_length=40)
    new_window_start: datetime
    new_window_end: datetime

    @model_validator(mode="after")
    def validate_window(self) -> TaskRescheduledPayload:
        if self.new_window_start.tzinfo is None or self.new_window_end.tzinfo is None:
            raise ValueError("改期时间必须包含时区偏移")
        if self.new_window_end <= self.new_window_start:
            raise ValueError("改期结束时间必须晚于开始时间")
        return self


class TaskCancelledPayload(StrictModel):
    task_id: str = Field(min_length=1, max_length=40)
    reason: str = Field(default="", max_length=300)


class TaskAddedPayload(StrictModel):
    visit: VisitTaskCreate


class TaskExtendedPayload(StrictModel):
    task_id: str = Field(min_length=1, max_length=40)
    new_duration_minutes: int = Field(ge=15, le=720)


class BudgetChangedPayload(StrictModel):
    hotel_nightly_cap_yuan: int | None = Field(default=None, gt=0, le=10_000)
    meal_daily_cap_yuan: int | None = Field(default=None, gt=0, le=5_000)
    local_transport_daily_cap_yuan: int | None = Field(default=None, gt=0, le=5_000)
    trip_total_cap_yuan: int | None = Field(default=None, gt=0, le=1_000_000)

    @model_validator(mode="after")
    def at_least_one_cap(self) -> BudgetChangedPayload:
        if all(
            value is None
            for value in (
                self.hotel_nightly_cap_yuan,
                self.meal_daily_cap_yuan,
                self.local_transport_daily_cap_yuan,
                self.trip_total_cap_yuan,
            )
        ):
            raise ValueError("预算变更至少包含一项额度")
        return self


class PreferenceChangedPayload(StrictModel):
    transport_preferences: TransportPreferences


class TransportDisruptionPayload(StrictModel):
    provider: str = Field(min_length=1, max_length=60)
    candidate_id: str = Field(min_length=1, max_length=120)
    status: Literal["delayed", "cancelled", "unavailable"]
    estimated_delay_minutes: int | None = Field(default=None, ge=0, le=1440)


class WeatherRiskPayload(StrictModel):
    location: str = Field(min_length=1, max_length=240)
    severity: Literal["medium", "high"]
    affected_task_ids: list[str] = Field(default_factory=list, max_length=6)
    summary: str = Field(min_length=1, max_length=500)


_EVENT_PAYLOAD_MODELS: dict[ReplanEventType, type[StrictModel]] = {
    ReplanEventType.TASK_RESCHEDULED: TaskRescheduledPayload,
    ReplanEventType.TASK_CANCELLED: TaskCancelledPayload,
    ReplanEventType.TASK_ADDED: TaskAddedPayload,
    ReplanEventType.TASK_EXTENDED: TaskExtendedPayload,
    ReplanEventType.BUDGET_CHANGED: BudgetChangedPayload,
    ReplanEventType.PREFERENCE_CHANGED: PreferenceChangedPayload,
    ReplanEventType.TRANSPORT_DISRUPTION: TransportDisruptionPayload,
    ReplanEventType.WEATHER_RISK: WeatherRiskPayload,
}


class ReplanEventCreate(StrictModel):
    event_id: str = Field(min_length=8, max_length=120)
    event_type: ReplanEventType
    based_on_revision: int | None = Field(default=None, ge=1)
    payload: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_payload_for_event(self) -> ReplanEventCreate:
        payload_model = _EVENT_PAYLOAD_MODELS[self.event_type]
        validated = payload_model.model_validate(self.payload)
        self.payload = validated.model_dump(mode="json")
        return self


class ReplanEventRead(StrictModel):
    event_id: str
    mission_id: str
    event_type: ReplanEventType
    based_on_revision: int | None
    accepted: bool
    idempotent_replay: bool
    created_at: datetime
