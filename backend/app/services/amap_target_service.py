from __future__ import annotations

from time import perf_counter

import requests

from app.config import settings
from app.models import FieldTaskRequest, GeoPoint, TargetPlace, ToolStatus


class AmapTargetService:
    search_url = "https://restapi.amap.com/v3/place/text"
    static_map_url = "https://restapi.amap.com/v3/staticmap"

    def discover(self, request: FieldTaskRequest) -> tuple[list[TargetPlace], ToolStatus]:
        started = perf_counter()
        if settings.use_mock_tools or not settings.amap_api_key:
            targets = self._mock_targets(request)
            return targets, ToolStatus(
                tool="target_discovery",
                status="mock",
                detail="使用可复现的上海合成点位；未调用高德 Web 服务。",
                elapsed_ms=self._elapsed(started),
            )

        try:
            targets = self._search_amap(request)
            if not targets:
                raise RuntimeError("高德未返回可用点位")
            return targets, ToolStatus(
                tool="target_discovery",
                status="success",
                detail=f"高德返回并去重得到 {len(targets)} 个目标点位。",
                elapsed_ms=self._elapsed(started),
            )
        except (requests.RequestException, RuntimeError, ValueError, KeyError) as exc:
            targets = self._mock_targets(request)
            return targets, ToolStatus(
                tool="target_discovery",
                status="degraded",
                detail=f"高德查询失败，已回退合成点位：{type(exc).__name__}",
                elapsed_ms=self._elapsed(started),
            )

    def build_static_map_url(self, targets: list[TargetPlace]) -> str | None:
        if not settings.amap_api_key or not targets:
            return None
        markers = "|".join(
            f"mid,0x2563eb,{index + 1}:{target.location.longitude},{target.location.latitude}"
            for index, target in enumerate(targets[:10])
        )
        return (
            f"{self.static_map_url}?key={settings.amap_api_key}"
            f"&size=900*520&zoom=10&markers={markers}"
        )

    def _search_amap(self, request: FieldTaskRequest) -> list[TargetPlace]:
        collected: list[TargetPlace] = []
        seen: set[tuple[str, str]] = set()
        for target_type in request.target_place_types:
            response = requests.get(
                self.search_url,
                params={
                    "key": settings.amap_api_key,
                    "city": request.city,
                    "citylimit": "true",
                    "keywords": f"{request.industry} {target_type}",
                    "offset": 10,
                    "page": 1,
                    "extensions": "base",
                },
                timeout=8,
            )
            response.raise_for_status()
            payload = response.json()
            if payload.get("status") != "1":
                raise RuntimeError(payload.get("info") or "高德接口返回失败")
            for poi in payload.get("pois", []):
                location = self._parse_location(poi.get("location"))
                name = str(poi.get("name") or "").strip()
                address = str(poi.get("address") or "地址待核验").strip()
                key = (name, address)
                if not name or location is None or key in seen:
                    continue
                seen.add(key)
                collected.append(
                    TargetPlace(
                        target_id=f"amap-{poi.get('id') or len(collected) + 1}",
                        name=name,
                        category=target_type,
                        address=address,
                        location=location,
                        task_brief=f"围绕“{request.objective}”完成现场观察、要点记录与证据归档。",
                        evidence_source="amap",
                        source_reference=str(poi.get("id") or "") or None,
                    )
                )
                if len(collected) >= 12:
                    return collected
        return collected

    @staticmethod
    def _parse_location(value: object) -> GeoPoint | None:
        if not isinstance(value, str) or "," not in value:
            return None
        longitude, latitude = value.split(",", maxsplit=1)
        return GeoPoint(longitude=float(longitude), latitude=float(latitude))

    @staticmethod
    def _elapsed(started: float) -> int:
        return max(round((perf_counter() - started) * 1000), 0)

    @staticmethod
    def _mock_targets(request: FieldTaskRequest) -> list[TargetPlace]:
        fixtures = [
            ("虹桥商务区样本门店 A", "闵行区申长路 688 号", 121.3188, 31.1941),
            ("徐家汇核心商圈样本门店 B", "徐汇区虹桥路 1 号", 121.4365, 31.1885),
            ("陆家嘴商圈样本门店 C", "浦东新区世纪大道 100 号", 121.5059, 31.2397),
            ("五角场商圈样本门店 D", "杨浦区淞沪路 77 号", 121.5144, 31.3007),
            ("静安商圈样本门店 E", "静安区南京西路 1000 号", 121.4553, 31.2294),
            ("中山公园商圈样本门店 F", "长宁区长宁路 1018 号", 121.4159, 31.2182),
            ("前滩商务区样本门店 G", "浦东新区东育路 500 号", 121.4782, 31.1511),
            ("大宁商圈样本门店 H", "静安区共和新路 1968 号", 121.4476, 31.2794),
        ]
        target_types = request.target_place_types
        return [
            TargetPlace(
                target_id=f"synthetic-sh-{index + 1:02d}",
                name=name,
                category=target_types[index % len(target_types)],
                address=address,
                location=GeoPoint(longitude=longitude, latitude=latitude),
                task_brief=(
                    f"围绕“{request.objective}”记录点位特征、客流线索、竞品分布与待复核事项。"
                ),
                evidence_source="synthetic",
                source_reference="examples/shanghai-field-task.json",
            )
            for index, (name, address, longitude, latitude) in enumerate(fixtures)
        ]
