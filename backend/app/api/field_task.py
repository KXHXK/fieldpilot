from fastapi import APIRouter

from app.agents import FieldPilotCoordinator
from app.models import FieldTaskPlan, FieldTaskRequest

router = APIRouter(prefix="/field-task", tags=["field-task"])


@router.post("/plan", response_model=FieldTaskPlan)
async def create_field_task_plan(request: FieldTaskRequest) -> FieldTaskPlan:
    return await FieldPilotCoordinator().run(request)
