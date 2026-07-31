from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import Field, model_validator

from app.domain.mission import LocationInput, StrictModel


class SourceMode(StrEnum):
    LIVE = "live"
    MIXED = "mixed"
    STALE = "stale"
    MANUAL = "manual"
    FIXTURE = "fixture"
    UNAVAILABLE = "unavailable"


class TransportMode(StrEnum):
    RAIL = "rail"
    FLIGHT = "flight"
    TRANSIT = "transit"
    TAXI = "taxi"
    WALKING = "walking"
    BICYCLING = "bicycling"


class MealType(StrEnum):
    BREAKFAST = "breakfast"
    LUNCH = "lunch"
    DINNER = "dinner"


class SegmentType(StrEnum):
    INTERCITY_TRANSPORT = "intercity_transport"
    LOCAL_TRANSPORT = "local_transport"
    VISIT = "visit"
    LODGING = "lodging"
    MEAL_ALLOWANCE = "meal_allowance"
    BUFFER = "buffer"


class PolicyStatus(StrEnum):
    PASS = "pass"
    FAIL = "fail"
    WARNING = "warning"


class RevisionStatus(StrEnum):
    PROPOSED = "proposed"
    ACTIVE = "active"
    SUPERSEDED = "superseded"
    REJECTED = "rejected"


class TransportCandidate(StrictModel):
    candidate_id: str
    provider: str
    source_mode: SourceMode
    mode: TransportMode
    direction: str
    from_ref: str
    to_ref: str
    depart_at: datetime
    arrive_at: datetime
    price_yuan: int = Field(ge=0)
    cabin_class: str | None = None
    transfers: int = Field(default=0, ge=0, le=8)
    reliability_score: int = Field(default=80, ge=0, le=100)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_timing(self) -> TransportCandidate:
        if self.depart_at.tzinfo is None or self.arrive_at.tzinfo is None:
            raise ValueError("候选交通时间必须包含时区")
        if self.arrive_at <= self.depart_at:
            raise ValueError("交通到达时间必须晚于出发时间")
        return self


class StayCandidate(StrictModel):
    candidate_id: str
    provider: str
    source_mode: SourceMode
    name: str
    address: str
    city: str
    nightly_price_yuan: int = Field(gt=0)
    rating: float | None = Field(default=None, ge=0, le=5)
    metadata: dict[str, Any] = Field(default_factory=dict)


class MealCandidate(StrictModel):
    candidate_id: str
    provider: str
    source_mode: SourceMode
    meal_type: MealType
    anchor_ref: str
    name: str
    address: str
    estimated_cost_yuan: int = Field(gt=0)
    service_minutes: int = Field(default=30, ge=15, le=120)
    distance_meters: int | None = Field(default=None, ge=0, le=50_000)
    rating: float | None = Field(default=None, ge=0, le=5)
    metadata: dict[str, Any] = Field(default_factory=dict)


class CandidateBundle(StrictModel):
    provider: str
    source_mode: SourceMode
    fetched_at: datetime
    query_fingerprint: str
    outbound: list[TransportCandidate]
    returns: list[TransportCandidate]
    stays: list[StayCandidate]
    reference_locations: dict[str, LocationInput] = Field(default_factory=dict)
    assumptions: list[str] = Field(default_factory=list)


class PlanSegment(StrictModel):
    segment_id: str
    segment_type: SegmentType
    title: str
    from_ref: str | None = None
    to_ref: str | None = None
    start_at: datetime
    end_at: datetime
    cost_yuan: int = Field(ge=0)
    provider: str
    source_mode: SourceMode
    candidate_id: str | None = None
    task_id: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_timing(self) -> PlanSegment:
        if self.start_at.tzinfo is None or self.end_at.tzinfo is None:
            raise ValueError("计划段时间必须包含时区")
        if self.end_at <= self.start_at:
            raise ValueError("计划段结束时间必须晚于开始时间")
        return self


class CostLedger(StrictModel):
    intercity_transport_yuan: int = Field(ge=0)
    local_transport_yuan: int = Field(ge=0)
    lodging_yuan: int = Field(ge=0)
    meals_yuan: int = Field(ge=0)
    planned_total_yuan: int = Field(ge=0)
    policy_total_cap_yuan: int = Field(gt=0)
    remaining_yuan: int

    @model_validator(mode="after")
    def validate_total(self) -> CostLedger:
        calculated = (
            self.intercity_transport_yuan
            + self.local_transport_yuan
            + self.lodging_yuan
            + self.meals_yuan
        )
        if calculated != self.planned_total_yuan:
            raise ValueError("费用总额与分类明细不一致")
        if self.policy_total_cap_yuan - calculated != self.remaining_yuan:
            raise ValueError("预算余量计算不一致")
        return self


class PolicyDecision(StrictModel):
    rule_id: str
    status: PolicyStatus
    observed: str
    limit: str
    explanation: str


class ScoreBreakdown(StrictModel):
    lateness_risk: float = Field(ge=0, le=100)
    cost: float = Field(ge=0, le=100)
    transfer_burden: float = Field(ge=0, le=100)
    walking: float = Field(ge=0, le=100)
    policy_margin: float = Field(ge=0, le=100)
    total: float = Field(ge=0, le=100)


class PlanOption(StrictModel):
    option_id: str
    label: str
    summary: str
    segments: list[PlanSegment]
    costs: CostLedger
    policy_decisions: list[PolicyDecision]
    score: ScoreBreakdown
    warnings: list[str] = Field(default_factory=list)


class PlanBundle(StrictModel):
    mission_id: str
    preferred_option_id: str
    options: list[PlanOption] = Field(min_length=1, max_length=3)
    provider_snapshot_ids: list[str]
    generated_at: datetime
    planner_version: str
    verifier_version: str


class PlanGenerationRequest(StrictModel):
    request_id: str = Field(min_length=8, max_length=120)
    based_on_revision: int | None = Field(default=None, ge=1)
    input_event_id: str | None = Field(default=None, min_length=8, max_length=120)


class PlanRevisionRead(StrictModel):
    revision_id: str
    mission_id: str
    revision: int
    based_on_revision: int | None
    request_id: str
    input_event_id: str | None
    status: RevisionStatus
    bundle: PlanBundle
    idempotent_replay: bool = False
    created_at: datetime


class SegmentChange(StrictModel):
    identity: str
    change_type: str
    before: PlanSegment | None = None
    after: PlanSegment | None = None


class RevisionDiffRead(StrictModel):
    mission_id: str
    from_revision: int
    to_revision: int
    input_event_id: str | None
    changes: list[SegmentChange]
    preserved_segment_count: int = Field(ge=0)
    cost_delta_yuan: int
    score_delta: float
    warnings_added: list[str] = Field(default_factory=list)
    warnings_removed: list[str] = Field(default_factory=list)


class ActivateRevisionRequest(StrictModel):
    expected_active_revision: int | None = Field(default=None, ge=1)


class RevisionActivationRead(StrictModel):
    mission_id: str
    active_revision: int
    status: RevisionStatus
    idempotent_replay: bool
