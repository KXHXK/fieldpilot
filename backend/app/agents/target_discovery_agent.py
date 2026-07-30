from app.models import FieldTaskRequest, TargetPlace, ToolStatus
from app.services import AmapTargetService


class TargetDiscoveryAgent:
    """Discover, normalize and deduplicate candidate field targets."""

    def __init__(self, service: AmapTargetService | None = None) -> None:
        self.service = service or AmapTargetService()

    def run(self, request: FieldTaskRequest) -> tuple[list[TargetPlace], ToolStatus]:
        targets, status = self.service.discover(request)
        unique: list[TargetPlace] = []
        seen: set[tuple[str, str]] = set()
        for target in targets:
            key = (target.name.strip().lower(), target.address.strip().lower())
            if key in seen:
                continue
            seen.add(key)
            unique.append(target)
        return unique, status
