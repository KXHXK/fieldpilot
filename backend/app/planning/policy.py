from __future__ import annotations

from collections import defaultdict
from zoneinfo import ZoneInfo

from app.domain import (
    CostLedger,
    ExpensePolicyRead,
    PlanSegment,
    PolicyDecision,
    PolicyStatus,
    SegmentType,
    StayCandidate,
    TransportCandidate,
    TransportMode,
)


class PolicyEngine:
    version = "policy-v2"

    @staticmethod
    def allows_transport(
        candidate: TransportCandidate,
        policy: ExpensePolicyRead,
    ) -> bool:
        if candidate.mode == TransportMode.RAIL:
            return candidate.cabin_class in policy.allowed_rail_classes
        if candidate.mode == TransportMode.FLIGHT:
            return candidate.cabin_class in policy.allowed_flight_classes
        return True

    @staticmethod
    def allows_stay(candidate: StayCandidate, policy: ExpensePolicyRead) -> bool:
        return candidate.nightly_price_yuan <= policy.hotel_nightly_cap_yuan

    def evaluate(
        self,
        *,
        segments: list[PlanSegment],
        costs: CostLedger,
        policy: ExpensePolicyRead,
        timezone_name: str,
    ) -> list[PolicyDecision]:
        decisions: list[PolicyDecision] = []
        rail_classes = sorted(
            {
                str(segment.metadata.get("cabin_class"))
                for segment in segments
                if segment.metadata.get("mode") == TransportMode.RAIL.value
            }
        )
        flight_classes = sorted(
            {
                str(segment.metadata.get("cabin_class"))
                for segment in segments
                if segment.metadata.get("mode") == TransportMode.FLIGHT.value
            }
        )
        decisions.append(
            self._membership_decision(
                "rail_class",
                rail_classes,
                policy.allowed_rail_classes,
                "高铁席别",
            )
        )
        decisions.append(
            self._membership_decision(
                "flight_class",
                flight_classes,
                policy.allowed_flight_classes,
                "航班舱位",
            )
        )

        nightly_prices = [
            int(segment.metadata.get("nightly_price_yuan", segment.cost_yuan))
            for segment in segments
            if segment.segment_type == SegmentType.LODGING
        ]
        max_nightly = max(nightly_prices, default=0)
        decisions.append(
            self._cap_decision(
                "hotel_nightly_cap",
                max_nightly,
                policy.hotel_nightly_cap_yuan,
                "单晚住宿",
            )
        )

        zone = ZoneInfo(timezone_name)
        local_by_day: dict[str, int] = defaultdict(int)
        meals_by_day: dict[str, int] = defaultdict(int)
        for segment in segments:
            day = segment.start_at.astimezone(zone).date().isoformat()
            if segment.segment_type == SegmentType.LOCAL_TRANSPORT:
                local_by_day[day] += segment.cost_yuan
            elif segment.segment_type == SegmentType.MEAL_ALLOWANCE:
                meals_by_day[day] += segment.cost_yuan
        max_local = max(local_by_day.values(), default=0)
        max_meal = max(meals_by_day.values(), default=0)
        decisions.append(
            self._cap_decision(
                "local_transport_daily_cap",
                max_local,
                policy.local_transport_daily_cap_yuan,
                "单日市内交通",
            )
        )
        decisions.append(
            self._cap_decision(
                "meal_daily_cap",
                max_meal,
                policy.meal_daily_cap_yuan,
                "单日餐饮预估",
            )
        )
        decisions.append(
            self._cap_decision(
                "trip_total_cap",
                costs.planned_total_yuan,
                policy.trip_total_cap_yuan,
                "行程总预算",
            )
        )
        return decisions

    @staticmethod
    def is_compliant(decisions: list[PolicyDecision]) -> bool:
        return all(decision.status != PolicyStatus.FAIL for decision in decisions)

    @staticmethod
    def _membership_decision(
        rule_id: str,
        observed: list[str],
        allowed: list[str],
        label: str,
    ) -> PolicyDecision:
        invalid = sorted(set(observed) - set(allowed))
        status = PolicyStatus.FAIL if invalid else PolicyStatus.PASS
        observed_text = ", ".join(observed) if observed else "未使用"
        explanation = (
            f"{label}均在允许范围内。"
            if not invalid
            else f"{label}包含不允许的等级：{', '.join(invalid)}。"
        )
        return PolicyDecision(
            rule_id=rule_id,
            status=status,
            observed=observed_text,
            limit=", ".join(allowed),
            explanation=explanation,
        )

    @staticmethod
    def _cap_decision(
        rule_id: str,
        observed: int,
        limit: int,
        label: str,
    ) -> PolicyDecision:
        status = PolicyStatus.PASS if observed <= limit else PolicyStatus.FAIL
        return PolicyDecision(
            rule_id=rule_id,
            status=status,
            observed=f"{observed} 元",
            limit=f"{limit} 元",
            explanation=(
                f"{label}未超过上限。"
                if status == PolicyStatus.PASS
                else f"{label}超过上限 {observed - limit} 元。"
            ),
        )
