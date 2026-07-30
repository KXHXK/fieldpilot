from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from time import perf_counter

from app.config import settings
from app.models import FieldRisk, FieldTaskRequest, ToolStatus


class WeatherRiskService:
    def assess(self, request: FieldTaskRequest) -> tuple[list[FieldRisk], ToolStatus]:
        started = perf_counter()
        dates = [
            request.start_date + timedelta(days=offset)
            for offset in range((request.end_date - request.start_date).days + 1)
        ]
        if settings.use_mock_tools or not settings.tavily_api_key:
            return self._mock_risks(dates), ToolStatus(
                tool="field_risk",
                status="mock",
                detail="使用固定环境风险样例；未调用 Tavily。",
                elapsed_ms=self._elapsed(started),
            )

        try:
            from tavily import TavilyClient

            client = TavilyClient(api_key=settings.tavily_api_key)
            with ThreadPoolExecutor(max_workers=min(3, len(dates))) as executor:
                risks = list(executor.map(lambda item: self._query_one(client, request.city, item), dates))
            return risks, ToolStatus(
                tool="field_risk",
                status="success",
                detail=f"并发检索 {len(dates)} 天环境信息并生成执行风险。",
                elapsed_ms=self._elapsed(started),
            )
        except Exception as exc:  # provider SDK and network exceptions vary by version
            return self._mock_risks(dates), ToolStatus(
                tool="field_risk",
                status="degraded",
                detail=f"环境信息查询失败，已回退固定样例：{type(exc).__name__}",
                elapsed_ms=self._elapsed(started),
            )

    @staticmethod
    def _query_one(client: object, city: str, date_value) -> FieldRisk:
        response = client.search(
            query=f"{city} {date_value.isoformat()} 天气 降雨 大风 高温",
            max_results=3,
            timeout=8,
        )
        text = " ".join(
            str(item.get("content", "")) for item in response.get("results", [])
        )
        high_markers = ("暴雨", "台风", "红色预警", "极端高温")
        medium_markers = ("降雨", "大风", "高温", "雷阵雨")
        if any(marker in text for marker in high_markers):
            level = "high"
            risk = "环境条件可能显著影响跨区域执行与现场停留。"
            mitigation = "缩短户外停留，预留改期窗口，并由负责人二次确认。"
        elif any(marker in text for marker in medium_markers):
            level = "medium"
            risk = "环境条件可能增加移动时间或影响现场记录。"
            mitigation = "预留 30 分钟缓冲，准备雨具并优先安排室内点位。"
        else:
            level = "low"
            risk = "未检索到明显环境阻断信号。"
            mitigation = "按计划执行，出发前再次核验实时预警。"
        return FieldRisk(
            date=date_value,
            level=level,
            weather_summary=(text[:180] or "已完成检索，未获得足够摘要。"),
            execution_risk=risk,
            mitigation=mitigation,
            evidence_source="tavily",
        )

    @staticmethod
    def _mock_risks(dates: list) -> list[FieldRisk]:
        templates = [
            ("low", "多云，体感适中", "跨区域移动风险较低。", "按计划执行，出发前复核实时预警。"),
            ("medium", "午后可能有短时阵雨", "雨天可能增加移动与拍摄记录难度。", "优先室内点位，预留 30 分钟缓冲并携带雨具。"),
            ("low", "晴到多云", "未发现明显环境阻断信号。", "关注高峰交通，保持点位间机动时间。"),
        ]
        return [
            FieldRisk(
                date=date_value,
                level=templates[index % len(templates)][0],
                weather_summary=templates[index % len(templates)][1],
                execution_risk=templates[index % len(templates)][2],
                mitigation=templates[index % len(templates)][3],
                evidence_source="synthetic",
            )
            for index, date_value in enumerate(dates)
        ]

    @staticmethod
    def _elapsed(started: float) -> int:
        return max(round((perf_counter() - started) * 1000), 0)
