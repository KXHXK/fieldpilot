from __future__ import annotations

import asyncio
import hashlib
from dataclasses import dataclass, replace
from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

from app.domain import (
    CandidateBundle,
    CostLedger,
    MissionRead,
    PlanOption,
    PlanSegment,
    ScoreBreakdown,
    SegmentType,
    SourceMode,
    StayCandidate,
    TransportCandidate,
    TransportMode,
    Urgency,
    VisitTaskRead,
)
from app.planning.policy import PolicyEngine
from app.providers.base import CandidateProvider


class NoFeasiblePlanError(RuntimeError):
    def __init__(self, reasons: list[str]) -> None:
        self.reasons = reasons
        super().__init__("没有满足当前时间窗与报销规则的方案")


@dataclass(frozen=True)
class _SearchState:
    segments: tuple[PlanSegment, ...]
    current_ref: str
    available_at: datetime
    remaining: tuple[VisitTaskRead, ...]
    hotel: StayCandidate | None
    min_slack_minutes: int
    walking_minutes: int
    transfer_count: int


class BoundedMissionPlanner:
    version = "bounded-beam-v1"

    def __init__(
        self,
        provider: CandidateProvider,
        policy_engine: PolicyEngine,
        *,
        beam_width: int = 24,
    ) -> None:
        self.provider = provider
        self.policy_engine = policy_engine
        self.beam_width = beam_width

    async def plan(
        self,
        mission: MissionRead,
        bundle: CandidateBundle,
    ) -> list[PlanOption]:
        policy = mission.expense_policy
        outbound = [
            candidate
            for candidate in bundle.outbound
            if self.policy_engine.allows_transport(candidate, policy)
        ]
        returns = [
            candidate
            for candidate in bundle.returns
            if self.policy_engine.allows_transport(candidate, policy)
        ]
        needs_lodging = mission.end_date > mission.start_date
        stays: list[StayCandidate | None]
        if needs_lodging:
            stays = [
                stay
                for stay in bundle.stays
                if self.policy_engine.allows_stay(stay, policy)
            ]
        else:
            stays = [None]
        reasons: list[str] = []
        if not outbound:
            reasons.append("没有符合交通等级政策的去程候选")
        if not returns:
            reasons.append("没有符合交通等级政策的返程候选")
        if needs_lodging and not stays:
            reasons.append("没有符合单晚住宿上限的酒店候选")
        if reasons:
            raise NoFeasiblePlanError(reasons)

        states: list[_SearchState] = []
        for candidate in outbound:
            for hotel in stays:
                states.append(
                    _SearchState(
                        segments=(self._transport_segment(candidate),),
                        current_ref=candidate.to_ref,
                        available_at=candidate.arrive_at,
                        remaining=tuple(mission.visits),
                        hotel=hotel,
                        min_slack_minutes=24 * 60,
                        walking_minutes=0,
                        transfer_count=candidate.transfers,
                    )
                )

        for _ in range(len(mission.visits)):
            batches = await asyncio.gather(
                *[
                    self._append_visit(mission, bundle, state, visit)
                    for state in states
                    for visit in state.remaining
                ]
            )
            expanded = [item for batch in batches for item in batch]
            if not expanded:
                raise NoFeasiblePlanError(
                    ["任务时间窗、交通耗时和必要缓冲无法同时满足"]
                )
            states = sorted(expanded, key=self._state_heuristic)[: self.beam_width]

        options: list[PlanOption] = []
        signatures: set[tuple[str, ...]] = set()
        finalized_states = await asyncio.gather(
            *[
                self._append_return(mission, bundle, state, return_candidate)
                for state in states
                for return_candidate in returns
            ]
        )
        for finalized in finalized_states:
            if finalized is None:
                continue
            option = self._to_option(mission, finalized, bundle)
            if option is None:
                continue
            signature = tuple(
                segment.candidate_id or segment.task_id or segment.segment_id
                for segment in option.segments
                if segment.segment_type
                in {
                    SegmentType.INTERCITY_TRANSPORT,
                    SegmentType.VISIT,
                    SegmentType.LODGING,
                }
            )
            if signature in signatures:
                continue
            signatures.add(signature)
            options.append(option)

        if not options:
            raise NoFeasiblePlanError(
                ["返程连接、分类额度或总预算使所有候选失效"]
            )
        options.sort(key=lambda item: item.score.total)
        labels = ["推荐方案", "备选方案 A", "备选方案 B"]
        return [
            option.model_copy(update={"label": labels[index]})
            for index, option in enumerate(options[:3])
        ]

    async def _append_visit(
        self,
        mission: MissionRead,
        bundle: CandidateBundle,
        state: _SearchState,
        visit: VisitTaskRead,
    ) -> list[_SearchState]:
        prepared = await self._advance_overnight(
            mission,
            bundle,
            state,
            visit.window_start.astimezone(ZoneInfo(mission.timezone)).date(),
        )
        if prepared is None:
            return []
        from_location = bundle.reference_locations.get(prepared.current_ref)
        to_location = bundle.reference_locations.get(visit.task_id)
        if from_location is None or to_location is None:
            return []
        routes = await self.provider.local_routes(
            prepared.current_ref,
            visit.task_id,
            from_location,
            to_location,
            prepared.available_at,
            mission.transport_preferences.preferred_local_modes,
            mission.timezone,
        )
        results: list[_SearchState] = []
        for route in routes:
            buffer_minutes = 30 if prepared.current_ref == "arrival-hub" else 15
            earliest_start = route.arrive_at + timedelta(minutes=buffer_minutes)
            visit_start = max(visit.window_start, earliest_start)
            visit_end = visit_start + timedelta(minutes=visit.duration_minutes)
            if visit_end > visit.window_end:
                continue
            segments = [*prepared.segments, self._transport_segment(route)]
            if visit_start > route.arrive_at:
                segments.append(
                    self._segment(
                        SegmentType.BUFFER,
                        f"任务前缓冲 {int((visit_start - route.arrive_at).total_seconds() // 60)} 分钟",
                        route.arrive_at,
                        visit_start,
                        provider="fieldpilot",
                        source_mode=SourceMode.MANUAL,
                        from_ref=visit.task_id,
                        to_ref=visit.task_id,
                    )
                )
            segments.append(
                self._segment(
                    SegmentType.VISIT,
                    visit.name,
                    visit_start,
                    visit_end,
                    provider="mission-input",
                    source_mode=SourceMode.MANUAL,
                    from_ref=visit.task_id,
                    to_ref=visit.task_id,
                    task_id=visit.task_id,
                    metadata={
                        "window_start": visit.window_start.isoformat(),
                        "window_end": visit.window_end.isoformat(),
                        "priority": visit.priority.value,
                    },
                )
            )
            slack = int((visit.window_end - visit_end).total_seconds() // 60)
            results.append(
                replace(
                    prepared,
                    segments=tuple(segments),
                    current_ref=visit.task_id,
                    available_at=visit_end,
                    remaining=tuple(
                        item for item in prepared.remaining if item.task_id != visit.task_id
                    ),
                    min_slack_minutes=min(prepared.min_slack_minutes, slack),
                    walking_minutes=(
                        prepared.walking_minutes
                        + self._walking_minutes(route)
                    ),
                    transfer_count=prepared.transfer_count + route.transfers,
                )
            )
        return results

    async def _append_return(
        self,
        mission: MissionRead,
        bundle: CandidateBundle,
        state: _SearchState,
        candidate: TransportCandidate,
    ) -> _SearchState | None:
        target_date = candidate.depart_at.astimezone(
            ZoneInfo(mission.timezone)
        ).date()
        prepared = await self._advance_overnight(mission, bundle, state, target_date)
        if prepared is None:
            return None
        from_location = bundle.reference_locations.get(prepared.current_ref)
        to_location = bundle.reference_locations.get(candidate.from_ref)
        if from_location is None or to_location is None:
            return None
        routes = await self.provider.local_routes(
            prepared.current_ref,
            candidate.from_ref,
            from_location,
            to_location,
            prepared.available_at,
            mission.transport_preferences.preferred_local_modes,
            mission.timezone,
        )
        feasible: list[tuple[int, TransportCandidate]] = []
        for route in routes:
            ready_at = route.arrive_at + timedelta(
                minutes=mission.transport_preferences.minimum_transfer_minutes
            )
            if ready_at <= candidate.depart_at:
                feasible.append((route.price_yuan, route))
        if not feasible:
            return None
        route = sorted(feasible, key=lambda item: item[0])[0][1]
        segments = [*prepared.segments, self._transport_segment(route)]
        if candidate.depart_at > route.arrive_at:
            segments.append(
                self._segment(
                    SegmentType.BUFFER,
                    "返程候车与换乘缓冲",
                    route.arrive_at,
                    candidate.depart_at,
                    provider="fieldpilot",
                    source_mode=SourceMode.MANUAL,
                    from_ref=candidate.from_ref,
                    to_ref=candidate.from_ref,
                )
            )
        segments.append(self._transport_segment(candidate))
        return replace(
            prepared,
            segments=tuple(segments),
            current_ref=candidate.to_ref,
            available_at=candidate.arrive_at,
            walking_minutes=prepared.walking_minutes + self._walking_minutes(route),
            transfer_count=prepared.transfer_count
            + route.transfers
            + candidate.transfers,
        )

    async def _advance_overnight(
        self,
        mission: MissionRead,
        bundle: CandidateBundle,
        state: _SearchState,
        target_date,
    ) -> _SearchState | None:
        zone = ZoneInfo(mission.timezone)
        prepared = state
        while prepared.available_at.astimezone(zone).date() < target_date:
            if prepared.hotel is None:
                return None
            hotel_ref = f"hotel:{prepared.hotel.candidate_id}"
            route = await self._best_local_route(
                mission,
                bundle,
                prepared.current_ref,
                hotel_ref,
                prepared.available_at,
            )
            if route is None:
                return None
            arrival_local = route.arrive_at.astimezone(zone)
            checkin_local = max(
                arrival_local,
                datetime.combine(arrival_local.date(), time(15, 0), tzinfo=zone),
            )
            checkout_local = datetime.combine(
                arrival_local.date() + timedelta(days=1),
                time(7, 30),
                tzinfo=zone,
            )
            segments = [*prepared.segments, self._transport_segment(route)]
            if checkin_local > arrival_local:
                segments.append(
                    self._segment(
                        SegmentType.BUFFER,
                        "酒店入住前可用缓冲",
                        route.arrive_at,
                        checkin_local,
                        provider="fieldpilot",
                        source_mode=SourceMode.MANUAL,
                        from_ref=hotel_ref,
                        to_ref=hotel_ref,
                    )
                )
            segments.append(
                self._segment(
                    SegmentType.LODGING,
                    prepared.hotel.name,
                    checkin_local,
                    checkout_local,
                    provider=prepared.hotel.provider,
                    source_mode=prepared.hotel.source_mode,
                    from_ref=hotel_ref,
                    to_ref=hotel_ref,
                    cost_yuan=prepared.hotel.nightly_price_yuan,
                    candidate_id=prepared.hotel.candidate_id,
                    metadata={
                        "address": prepared.hotel.address,
                        "nightly_price_yuan": prepared.hotel.nightly_price_yuan,
                    },
                )
            )
            prepared = replace(
                prepared,
                segments=tuple(segments),
                current_ref=hotel_ref,
                available_at=checkout_local,
                walking_minutes=prepared.walking_minutes
                + self._walking_minutes(route),
                transfer_count=prepared.transfer_count + route.transfers,
            )
        return prepared

    async def _best_local_route(
        self,
        mission: MissionRead,
        bundle: CandidateBundle,
        from_ref: str,
        to_ref: str,
        depart_at: datetime,
    ) -> TransportCandidate | None:
        from_location = bundle.reference_locations.get(from_ref)
        to_location = bundle.reference_locations.get(to_ref)
        if from_location is None or to_location is None:
            return None
        routes = await self.provider.local_routes(
            from_ref,
            to_ref,
            from_location,
            to_location,
            depart_at,
            mission.transport_preferences.preferred_local_modes,
            mission.timezone,
        )
        if not routes:
            return None
        if mission.urgency == Urgency.TIGHT:
            return min(routes, key=lambda item: (item.arrive_at, item.price_yuan))
        if mission.urgency == Urgency.FLEXIBLE:
            return min(routes, key=lambda item: (item.price_yuan, item.arrive_at))
        return min(
            routes,
            key=lambda item: (item.price_yuan + self._duration_minutes(item), item.arrive_at),
        )

    def _to_option(
        self,
        mission: MissionRead,
        state: _SearchState,
        bundle: CandidateBundle,
    ) -> PlanOption | None:
        segments = list(state.segments)
        intercity = sum(
            item.cost_yuan
            for item in segments
            if item.segment_type == SegmentType.INTERCITY_TRANSPORT
        )
        local = sum(
            item.cost_yuan
            for item in segments
            if item.segment_type == SegmentType.LOCAL_TRANSPORT
        )
        lodging = sum(
            item.cost_yuan
            for item in segments
            if item.segment_type == SegmentType.LODGING
        )
        meals = 0
        total = intercity + local + lodging + meals
        costs = CostLedger(
            intercity_transport_yuan=intercity,
            local_transport_yuan=local,
            lodging_yuan=lodging,
            meals_yuan=meals,
            planned_total_yuan=total,
            policy_total_cap_yuan=mission.expense_policy.trip_total_cap_yuan,
            remaining_yuan=mission.expense_policy.trip_total_cap_yuan - total,
        )
        decisions = self.policy_engine.evaluate(
            segments=segments,
            costs=costs,
            policy=mission.expense_policy,
            timezone_name=mission.timezone,
        )
        if not self.policy_engine.is_compliant(decisions):
            return None
        score = self._score(mission, state, costs)
        option_id = self._option_id(segments)
        return PlanOption(
            option_id=option_id,
            label="候选方案",
            summary=(
                f"完成 {len(mission.visits)} 个任务，计划费用 {total} 元，"
                f"最小任务余量 {state.min_slack_minutes} 分钟。"
            ),
            segments=segments,
            costs=costs,
            policy_decisions=decisions,
            score=score,
            warnings=[
                *bundle.assumptions,
                "尚未生成餐饮候选，餐饮费用暂记 0 元，不代表无需报销。",
                "尚未包含出发地到跨城交通枢纽的首段接驳。",
                *self._route_source_warnings(segments),
            ],
        )

    def _score(
        self,
        mission: MissionRead,
        state: _SearchState,
        costs: CostLedger,
    ) -> ScoreBreakdown:
        lateness_risk = max(0.0, 100.0 - min(state.min_slack_minutes, 120) / 1.2)
        cost = min(
            100.0,
            costs.planned_total_yuan / costs.policy_total_cap_yuan * 100,
        )
        transport_segments = sum(
            segment.segment_type
            in {SegmentType.INTERCITY_TRANSPORT, SegmentType.LOCAL_TRANSPORT}
            for segment in state.segments
        )
        transfer_burden = min(
            100.0, transport_segments * 8.0 + state.transfer_count * 12.0
        )
        walking = min(100.0, state.walking_minutes / 120 * 100)
        policy_margin = cost
        weights = {
            Urgency.TIGHT: (0.45, 0.20, 0.20, 0.10, 0.05),
            Urgency.BALANCED: (0.35, 0.30, 0.20, 0.10, 0.05),
            Urgency.FLEXIBLE: (0.25, 0.45, 0.15, 0.10, 0.05),
        }[mission.urgency]
        total = sum(
            value * weight
            for value, weight in zip(
                (lateness_risk, cost, transfer_burden, walking, policy_margin),
                weights,
                strict=True,
            )
        )
        return ScoreBreakdown(
            lateness_risk=round(lateness_risk, 2),
            cost=round(cost, 2),
            transfer_burden=round(transfer_burden, 2),
            walking=round(walking, 2),
            policy_margin=round(policy_margin, 2),
            total=round(total, 2),
        )

    @staticmethod
    def _state_heuristic(state: _SearchState) -> tuple[datetime, int, int]:
        cost = sum(segment.cost_yuan for segment in state.segments)
        return state.available_at, cost, -state.min_slack_minutes

    def _transport_segment(self, candidate: TransportCandidate) -> PlanSegment:
        segment_type = (
            SegmentType.INTERCITY_TRANSPORT
            if candidate.direction in {"outbound", "return"}
            else SegmentType.LOCAL_TRANSPORT
        )
        return self._segment(
            segment_type,
            f"{candidate.mode.value}：{candidate.from_ref} → {candidate.to_ref}",
            candidate.depart_at,
            candidate.arrive_at,
            provider=candidate.provider,
            source_mode=candidate.source_mode,
            from_ref=candidate.from_ref,
            to_ref=candidate.to_ref,
            cost_yuan=candidate.price_yuan,
            candidate_id=candidate.candidate_id,
            metadata={
                **candidate.metadata,
                "mode": candidate.mode.value,
                "cabin_class": candidate.cabin_class,
                "transfers": candidate.transfers,
                "reliability_score": candidate.reliability_score,
            },
        )

    @staticmethod
    def _route_source_warnings(segments: list[PlanSegment]) -> list[str]:
        local_segments = [
            segment
            for segment in segments
            if segment.segment_type == SegmentType.LOCAL_TRANSPORT
        ]
        fallback_reasons = sorted(
            {
                str(segment.metadata["fallback_reason"])
                for segment in local_segments
                if segment.metadata.get("fallback_reason")
            }
        )
        if fallback_reasons:
            return [
                "部分市内路线由高德失败后降级为 Fixture："
                + "、".join(fallback_reasons)
            ]
        if local_segments and all(
            segment.source_mode == SourceMode.FIXTURE for segment in local_segments
        ):
            return ["市内路线为冻结 Fixture，不代表实时路况或价格。"]
        return []

    def _segment(
        self,
        segment_type: SegmentType,
        title: str,
        start_at: datetime,
        end_at: datetime,
        *,
        provider: str,
        source_mode: SourceMode,
        from_ref: str | None = None,
        to_ref: str | None = None,
        cost_yuan: int = 0,
        candidate_id: str | None = None,
        task_id: str | None = None,
        metadata: dict | None = None,
    ) -> PlanSegment:
        identity = (
            f"{segment_type.value}|{start_at.isoformat()}|{end_at.isoformat()}|"
            f"{candidate_id}|{task_id}|{from_ref}|{to_ref}"
        )
        segment_id = f"seg-{hashlib.sha1(identity.encode('utf-8')).hexdigest()[:16]}"
        return PlanSegment(
            segment_id=segment_id,
            segment_type=segment_type,
            title=title,
            from_ref=from_ref,
            to_ref=to_ref,
            start_at=start_at,
            end_at=end_at,
            cost_yuan=cost_yuan,
            provider=provider,
            source_mode=source_mode,
            candidate_id=candidate_id,
            task_id=task_id,
            metadata=metadata or {},
        )

    @staticmethod
    def _option_id(segments: list[PlanSegment]) -> str:
        signature = "|".join(segment.segment_id for segment in segments)
        return f"opt-{hashlib.sha1(signature.encode('utf-8')).hexdigest()[:16]}"

    @staticmethod
    def _duration_minutes(candidate: TransportCandidate) -> int:
        return int((candidate.arrive_at - candidate.depart_at).total_seconds() // 60)

    def _walking_minutes(self, candidate: TransportCandidate) -> int:
        if candidate.mode != TransportMode.WALKING:
            return 0
        return self._duration_minutes(candidate)
