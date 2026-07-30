from datetime import timedelta
from time import perf_counter

from app.models import (
    DailyFieldPlan,
    FieldRisk,
    FieldTaskRequest,
    OperationBase,
    TargetPlace,
    ToolStatus,
)


class TaskPlanningAgent:
    """Build a bounded, non-repeating daily field schedule from verified inputs."""

    def run(
        self,
        request: FieldTaskRequest,
        targets: list[TargetPlace],
        risks: list[FieldRisk],
        operation_base: OperationBase,
    ) -> tuple[list[DailyFieldPlan], ToolStatus]:
        started = perf_counter()
        day_count = (request.end_date - request.start_date).days + 1
        selected = targets[: max(day_count, min(len(targets), day_count * 2))]
        buckets: list[list[TargetPlace]] = [[] for _ in range(day_count)]
        for index, target in enumerate(selected):
            buckets[index % day_count].append(target)

        risk_by_date = {risk.date: risk for risk in risks}
        days: list[DailyFieldPlan] = []
        for offset, day_targets in enumerate(buckets):
            date_value = request.start_date + timedelta(days=offset)
            risk = risk_by_date.get(date_value)
            risk_level = risk.level if risk else "medium"
            days.append(
                DailyFieldPlan(
                    day_index=offset + 1,
                    date=date_value,
                    summary=self._summary(day_targets, offset, day_count),
                    transport_guidance=self._transport(request.transport_type, risk_level),
                    base_guidance=(
                        f"从{operation_base.name}出发；结束后归档照片、访谈要点和待复核事项。"
                    ),
                    risk_level=risk_level,
                    targets=day_targets,
                )
            )
        return days, ToolStatus(
            tool="task_planning",
            status="success",
            detail=f"将 {len(selected)} 个去重点位分配到 {day_count} 天，未循环复用旧点位。",
            elapsed_ms=max(round((perf_counter() - started) * 1000), 0),
        )

    @staticmethod
    def _summary(targets: list[TargetPlace], offset: int, day_count: int) -> str:
        if not targets:
            return "当前无可用点位，保留为资料整理与补充核验时段。"
        phase = "建立样本基线" if offset == 0 else "补充区域对照"
        if offset == day_count - 1 and day_count > 1:
            phase = "完成交叉核验与收口"
        return f"{phase}：执行 {len(targets)} 个点位任务，现场记录后统一归档。"

    @staticmethod
    def _transport(transport_type: str, risk_level: str) -> str:
        transport = {
            "public_transport": "以轨道交通串联主要区域，单点结束后再确认下一段实时耗时。",
            "taxi": "以网约车衔接点位，保留高峰拥堵和上下客缓冲时间。",
            "walking": "仅串联相邻点位，单段步行建议控制在 20 分钟以内。",
        }[transport_type]
        if risk_level == "high":
            return f"{transport} 当前为高风险日期，须负责人确认后执行或改期。"
        if risk_level == "medium":
            return f"{transport} 额外预留 30 分钟环境与交通缓冲。"
        return transport
