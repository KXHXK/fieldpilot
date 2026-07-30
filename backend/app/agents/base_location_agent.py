from time import perf_counter

from app.models import FieldTaskRequest, GeoPoint, OperationBase, TargetPlace, ToolStatus


class BaseLocationAgent:
    """Choose a deterministic operating base from the candidate target centroid."""

    def run(
        self,
        request: FieldTaskRequest,
        targets: list[TargetPlace],
    ) -> tuple[OperationBase, ToolStatus]:
        started = perf_counter()
        if targets:
            longitude = sum(item.location.longitude for item in targets) / len(targets)
            latitude = sum(item.location.latitude for item in targets) / len(targets)
        else:
            longitude, latitude = 121.4737, 31.2304
        operation_base = OperationBase(
            name=f"{request.city}中心区域执行驻点（待预订）",
            address="建议在目标点位几何中心附近按实际价格二次筛选",
            location=GeoPoint(longitude=longitude, latitude=latitude),
            rationale=(
                f"根据 {len(targets)} 个候选点位中心位置，并结合“{request.base_preference}”生成；"
                "系统不代替实际住宿或会议地点预订。"
            ),
            estimated_nightly_cost=420,
        )
        return operation_base, ToolStatus(
            tool="base_selection",
            status="success",
            detail="使用点位中心与驻点偏好生成确定性建议。",
            elapsed_ms=max(round((perf_counter() - started) * 1000), 0),
        )
