from __future__ import annotations

from app.domain import (
    MissionRead,
    PlanOption,
    PolicyStatus,
    SegmentType,
)
from app.planning.policy import PolicyEngine


class PlanVerificationError(RuntimeError):
    def __init__(self, violations: list[str]) -> None:
        self.violations = violations
        super().__init__("；".join(violations))


class PlanVerifier:
    version = "plan-verifier-v1"

    def __init__(self, policy_engine: PolicyEngine) -> None:
        self.policy_engine = policy_engine

    def verify(self, mission: MissionRead, option: PlanOption) -> None:
        violations: list[str] = []
        segments = option.segments
        if not segments:
            violations.append("计划没有任何执行段")
        for previous, current in zip(segments, segments[1:]):
            if current.start_at < previous.end_at:
                violations.append(
                    f"计划段重叠：{previous.segment_id} 与 {current.segment_id}"
                )

        expected_tasks = {visit.task_id: visit for visit in mission.visits}
        visit_segments = [
            segment
            for segment in segments
            if segment.segment_type == SegmentType.VISIT
        ]
        observed_task_ids = [segment.task_id for segment in visit_segments]
        if set(observed_task_ids) != set(expected_tasks):
            violations.append("计划任务集合与 Mission 不一致")
        if len(observed_task_ids) != len(set(observed_task_ids)):
            violations.append("同一任务被重复安排")
        for segment in visit_segments:
            if segment.task_id not in expected_tasks:
                continue
            visit = expected_tasks[segment.task_id]
            if segment.start_at < visit.window_start or segment.end_at > visit.window_end:
                violations.append(f"任务 {visit.task_id} 超出允许时间窗")
            actual_minutes = int(
                (segment.end_at - segment.start_at).total_seconds() // 60
            )
            if actual_minutes != visit.duration_minutes:
                violations.append(f"任务 {visit.task_id} 持续时间不一致")

        calculated_intercity = sum(
            segment.cost_yuan
            for segment in segments
            if segment.segment_type == SegmentType.INTERCITY_TRANSPORT
        )
        calculated_local = sum(
            segment.cost_yuan
            for segment in segments
            if segment.segment_type == SegmentType.LOCAL_TRANSPORT
        )
        calculated_lodging = sum(
            segment.cost_yuan
            for segment in segments
            if segment.segment_type == SegmentType.LODGING
        )
        calculated_meals = sum(
            segment.cost_yuan
            for segment in segments
            if segment.segment_type == SegmentType.MEAL_ALLOWANCE
        )
        expected_costs = (
            calculated_intercity,
            calculated_local,
            calculated_lodging,
            calculated_meals,
        )
        actual_costs = (
            option.costs.intercity_transport_yuan,
            option.costs.local_transport_yuan,
            option.costs.lodging_yuan,
            option.costs.meals_yuan,
        )
        if expected_costs != actual_costs:
            violations.append("费用分类明细与计划段重新计算结果不一致")

        decisions = self.policy_engine.evaluate(
            segments=segments,
            costs=option.costs,
            policy=mission.expense_policy,
            timezone_name=mission.timezone,
        )
        failed = [
            decision.rule_id
            for decision in decisions
            if decision.status == PolicyStatus.FAIL
        ]
        if failed:
            violations.append(f"政策复核失败：{', '.join(failed)}")
        if [item.model_dump() for item in decisions] != [
            item.model_dump() for item in option.policy_decisions
        ]:
            violations.append("计划携带的政策判断与独立复算不一致")

        intercity_segments = [
            segment
            for segment in segments
            if segment.segment_type == SegmentType.INTERCITY_TRANSPORT
        ]
        if len(intercity_segments) < 2:
            violations.append("缺少完整去程或返程跨城交通")

        if violations:
            raise PlanVerificationError(violations)
