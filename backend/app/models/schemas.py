from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator


class GeoPoint(BaseModel):
    longitude: float = Field(ge=-180, le=180)
    latitude: float = Field(ge=-90, le=90)


class FieldTaskRequest(BaseModel):
    city: str = Field(min_length=1, max_length=40)
    start_date: date
    end_date: date
    industry: str = Field(min_length=1, max_length=80)
    target_place_types: list[str] = Field(min_length=1, max_length=5)
    objective: str = Field(min_length=5, max_length=500)
    budget: int = Field(gt=0, le=100_000)
    transport_type: Literal["public_transport", "taxi", "walking"] = "public_transport"
    base_preference: str = Field(default="靠近地铁，便于覆盖多个区域", max_length=200)

    @field_validator("target_place_types")
    @classmethod
    def normalize_target_types(cls, values: list[str]) -> list[str]:
        normalized = list(dict.fromkeys(value.strip() for value in values if value.strip()))
        if not normalized:
            raise ValueError("至少提供一种目标场所类型")
        return normalized

    @model_validator(mode="after")
    def validate_period(self) -> "FieldTaskRequest":
        if self.end_date < self.start_date:
            raise ValueError("结束日期不能早于开始日期")
        if (self.end_date - self.start_date).days > 6:
            raise ValueError("MVP 单次任务周期最多 7 天")
        return self


class TargetPlace(BaseModel):
    target_id: str
    name: str
    category: str
    address: str
    location: GeoPoint
    task_brief: str
    evidence_source: Literal["synthetic", "amap"]
    source_reference: str | None = None


class FieldRisk(BaseModel):
    date: date
    level: Literal["low", "medium", "high"]
    weather_summary: str
    execution_risk: str
    mitigation: str
    evidence_source: Literal["synthetic", "tavily"]


class OperationBase(BaseModel):
    name: str
    address: str
    location: GeoPoint
    rationale: str
    estimated_nightly_cost: int = Field(ge=0)


class DailyFieldPlan(BaseModel):
    day_index: int = Field(ge=1)
    date: date
    summary: str
    transport_guidance: str
    base_guidance: str
    risk_level: Literal["low", "medium", "high"]
    targets: list[TargetPlace]


class CostBreakdown(BaseModel):
    target_operations: int = Field(ge=0)
    lodging: int = Field(ge=0)
    meals: int = Field(ge=0)
    transportation: int = Field(ge=0)
    planned_total: int = Field(ge=0)
    budget_limit: int = Field(gt=0)
    remaining: int


class ToolStatus(BaseModel):
    tool: str
    status: Literal["success", "mock", "degraded"]
    detail: str
    elapsed_ms: int = Field(ge=0)


class FieldTaskPlan(BaseModel):
    task_id: str
    city: str
    start_date: date
    end_date: date
    industry: str
    objective: str
    overview: str
    operation_base: OperationBase
    risks: list[FieldRisk]
    days: list[DailyFieldPlan]
    costs: CostBreakdown
    tool_statuses: list[ToolStatus]
    warnings: list[str]
    generated_at: datetime
    map_image_url: str | None = None
