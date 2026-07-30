from datetime import date

import pytest

from app.agents import FieldPilotCoordinator
from app.models import FieldTaskRequest


@pytest.mark.asyncio
async def test_shanghai_plan_is_bounded_unique_and_auditable() -> None:
    request = FieldTaskRequest(
        city="上海",
        start_date=date(2026, 8, 1),
        end_date=date(2026, 8, 3),
        industry="新能源汽车",
        target_place_types=["品牌门店", "核心商圈"],
        objective="调研品牌门店分布与周边竞品",
        budget=3000,
        transport_type="public_transport",
        base_preference="靠近地铁，便于覆盖多个商圈",
    )

    plan = await FieldPilotCoordinator().run(request)

    target_ids = [target.target_id for day in plan.days for target in day.targets]
    assert len(plan.days) == 3
    assert len(target_ids) == 6
    assert len(target_ids) == len(set(target_ids))
    assert plan.costs.planned_total == (
        plan.costs.target_operations
        + plan.costs.lodging
        + plan.costs.meals
        + plan.costs.transportation
    )
    assert {status.tool for status in plan.tool_statuses} == {
        "field_risk",
        "target_discovery",
        "base_selection",
        "task_planning",
        "llm_summary",
    }
    assert plan.warnings
