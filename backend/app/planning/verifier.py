from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from app.domain import (
    MealType,
    MissionRead,
    PlanOption,
    PlanSegment,
    PolicyStatus,
    SegmentType,
)
from app.planning.policy import PolicyEngine


class PlanVerificationError(RuntimeError):
    def __init__(self, violations: list[str]) -> None:
        self.violations = violations
        super().__init__("；".join(violations))


class PlanVerifier:
    version = "plan-verifier-v3"

    def __init__(self, policy_engine: PolicyEngine) -> None:
        self.policy_engine = policy_engine

    def verify(
        self,
        mission: MissionRead,
        option: PlanOption,
        *,
        protected_prefix: list[PlanSegment] | None = None,
        resume_from_segment_id: str | None = None,
    ) -> None:
        violations: list[str] = []
        segments = option.segments
        if not segments:
            violations.append("计划没有任何执行段")
        exclusive_segments = sorted(
            (
                segment
                for segment in segments
                if segment.segment_type
                not in {SegmentType.BUFFER, SegmentType.LODGING}
            ),
            key=lambda segment: (segment.start_at, segment.end_at),
        )
        for previous, current in zip(
            exclusive_segments,
            exclusive_segments[1:],
        ):
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

        zone = ZoneInfo(mission.timezone)
        observed_meal_slots: set[tuple[str, str]] = set()
        valid_meal_types = {item.value for item in MealType}
        for segment in segments:
            if segment.segment_type != SegmentType.MEAL_ALLOWANCE:
                continue
            meal_type = str(segment.metadata.get("meal_type") or "")
            day = segment.start_at.astimezone(zone).date().isoformat()
            slot = (day, meal_type)
            if meal_type not in valid_meal_types:
                violations.append(f"餐饮段 {segment.segment_id} 缺少有效餐次")
            elif slot in observed_meal_slots:
                violations.append(f"{day} 的 {meal_type} 被重复安排")
            observed_meal_slots.add(slot)
            if not segment.candidate_id or segment.cost_yuan <= 0:
                violations.append(f"餐饮段 {segment.segment_id} 缺少候选或费用")
            anchor_ref = segment.metadata.get("anchor_ref")
            if not anchor_ref or segment.from_ref != anchor_ref or segment.to_ref != anchor_ref:
                violations.append(f"餐饮段 {segment.segment_id} 的就近锚点不一致")
            try:
                window_start = datetime.fromisoformat(
                    str(segment.metadata["meal_window_start"])
                )
                window_end = datetime.fromisoformat(
                    str(segment.metadata["meal_window_end"])
                )
            except (KeyError, TypeError, ValueError):
                violations.append(f"餐饮段 {segment.segment_id} 缺少有效时间窗")
            else:
                if segment.start_at < window_start or segment.end_at > window_end:
                    violations.append(f"餐饮段 {segment.segment_id} 超出餐次时间窗")

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

        if protected_prefix:
            protected_by_id = {
                segment.segment_id: segment for segment in protected_prefix
            }
            observed_by_id = {segment.segment_id: segment for segment in segments}
            if len(protected_by_id) != len(protected_prefix):
                violations.append("受保护前缀包含重复行程段")
            for segment_id, expected in protected_by_id.items():
                observed = observed_by_id.get(segment_id)
                if observed is None:
                    violations.append(f"受保护行程段 {segment_id} 被删除")
                elif observed.model_dump(mode="json") != expected.model_dump(
                    mode="json"
                ):
                    violations.append(f"受保护行程段 {segment_id} 被修改")
            checkpoint = protected_by_id.get(resume_from_segment_id or "")
            if checkpoint is None:
                violations.append("受保护前缀缺少执行检查点")
            else:
                protected_ids = set(protected_by_id)
                for segment in segments:
                    if (
                        segment.segment_id not in protected_ids
                        and segment.start_at < checkpoint.end_at
                    ):
                        violations.append(
                            f"后缀行程段 {segment.segment_id} 越过执行检查点"
                        )

        if violations:
            raise PlanVerificationError(violations)
