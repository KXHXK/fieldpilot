import asyncio
from datetime import datetime, timezone
from uuid import uuid4

from app.agents.base_location_agent import BaseLocationAgent
from app.agents.field_risk_agent import FieldRiskAgent
from app.agents.target_discovery_agent import TargetDiscoveryAgent
from app.agents.task_planning_agent import TaskPlanningAgent
from app.models import CostBreakdown, FieldTaskPlan, FieldTaskRequest, ToolStatus
from app.services import AmapTargetService, SummaryService


class FieldPilotCoordinator:
    """Coordinate deterministic tools and a bounded optional LLM summary."""

    def __init__(self) -> None:
        self.risk_agent = FieldRiskAgent()
        self.target_agent = TargetDiscoveryAgent()
        self.base_agent = BaseLocationAgent()
        self.planning_agent = TaskPlanningAgent()
        self.summary_service = SummaryService()
        self.map_service = AmapTargetService()

    async def run(self, request: FieldTaskRequest) -> FieldTaskPlan:
        (risks, risk_status), (targets, target_status) = await asyncio.gather(
            asyncio.to_thread(self.risk_agent.run, request),
            asyncio.to_thread(self.target_agent.run, request),
        )
        operation_base, base_status = self.base_agent.run(request, targets)
        days, planning_status = self.planning_agent.run(
            request=request,
            targets=targets,
            risks=risks,
            operation_base=operation_base,
        )
        overview, llm_status = await asyncio.to_thread(
            self.summary_service.summarize,
            request,
            days,
        )
        used_targets = [target for day in days for target in day.targets]
        statuses = [risk_status, target_status, base_status, planning_status, llm_status]
        return FieldTaskPlan(
            task_id=f"fp-{uuid4().hex[:12]}",
            city=request.city,
            start_date=request.start_date,
            end_date=request.end_date,
            industry=request.industry,
            objective=request.objective,
            overview=overview,
            operation_base=operation_base,
            risks=risks,
            days=days,
            costs=self._calculate_costs(request, len(used_targets)),
            tool_statuses=statuses,
            warnings=self._warnings(statuses),
            generated_at=datetime.now(timezone.utc),
            map_image_url=self.map_service.build_static_map_url(used_targets),
        )

    @staticmethod
    def _calculate_costs(request: FieldTaskRequest, target_count: int) -> CostBreakdown:
        day_count = (request.end_date - request.start_date).days + 1
        target_operations = target_count * 120
        lodging = max(day_count - 1, 1) * 420
        meals = day_count * 180
        transportation = day_count * {
            "public_transport": 80,
            "taxi": 220,
            "walking": 40,
        }[request.transport_type]
        planned_total = target_operations + lodging + meals + transportation
        return CostBreakdown(
            target_operations=target_operations,
            lodging=lodging,
            meals=meals,
            transportation=transportation,
            planned_total=planned_total,
            budget_limit=request.budget,
            remaining=request.budget - planned_total,
        )

    @staticmethod
    def _warnings(statuses: list[ToolStatus]) -> list[str]:
        warnings: list[str] = []
        if any(status.status == "mock" for status in statuses):
            warnings.append("当前包含演示数据或确定性摘要，适合本地复现，不应视为实时事实。")
        if any(status.status == "degraded" for status in statuses):
            warnings.append("部分外部能力已降级；完整点位、风险与预订信息须人工复核。")
        return warnings
