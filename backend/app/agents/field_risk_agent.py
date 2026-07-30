from app.models import FieldRisk, FieldTaskRequest, ToolStatus
from app.services import WeatherRiskService


class FieldRiskAgent:
    """Collect environmental evidence and translate it into bounded execution risks."""

    def __init__(self, service: WeatherRiskService | None = None) -> None:
        self.service = service or WeatherRiskService()

    def run(self, request: FieldTaskRequest) -> tuple[list[FieldRisk], ToolStatus]:
        return self.service.assess(request)
