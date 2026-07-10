from functools import lru_cache
from typing import Any
import base64
from urllib.parse import urlencode

import requests

from app.config import settings
from app.models import Attraction, Hotel, Location


class AmapMCPService:
    """Shared Amap service wrapper.

    这里仍然保留 Chapter 13.4 的 MCP 思路：业务层不直接散落调用高德接口，
    而是集中通过一个工具服务访问地点搜索、酒店搜索和地图能力。
    """

    def __init__(self, api_key: str, use_mock: bool = True):
        self.api_key = api_key
        self.use_mock = use_mock
        self.name = "amap_mcp"
        self.command = "npx"
        self.args = ["-y", "@sugarforever/amap-mcp-server"]
        self.base_url = "https://restapi.amap.com"

    def describe(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "command": self.command,
            "args": self.args,
            "auto_expand": True,
            "mock": self.use_mock,
            "has_api_key": bool(self.api_key),
        }

    def list_mock_tools(self) -> list[str]:
        return [
            "amap_maps_text_search",
            "amap_maps_geo",
            "amap_maps_direction_driving",
            "amap_maps_direction_walking",
        ]

    def get_adcode(self, city: str) -> str:
        if not self.api_key:
            return city

        response = requests.get(
            f"{self.base_url}/v3/geocode/geo",
            params={"key": self.api_key, "address": city},
            timeout=10,
        )
        response.raise_for_status()
        data = response.json()
        geocodes = data.get("geocodes", [])
        if not geocodes:
            return city
        return geocodes[0].get("adcode") or city

    def search_attractions(self, city: str, preferences: str, limit: int = 12) -> list[Attraction]:
        if self.use_mock or not self.api_key:
            return []

        collected: list[dict[str, Any]] = []
        seen_names: set[str] = set()
        for query in _build_attraction_queries(preferences):
            pois = self._search_pois(city=city, keywords=query, offset=limit)
            for poi in pois:
                name = poi.get("name") or ""
                if not name or name in seen_names:
                    continue
                seen_names.add(name)
                collected.append(poi)
                if len(collected) >= limit:
                    break
            if len(collected) >= limit:
                break

        attractions: list[Attraction] = []
        for poi in collected[:limit]:
            location = _parse_location(poi.get("location"))
            if location is None:
                continue
            biz_ext = poi.get("biz_ext") if isinstance(poi.get("biz_ext"), dict) else {}
            photos = poi.get("photos") if isinstance(poi.get("photos"), list) else []
            first_photo = photos[0] if photos and isinstance(photos[0], dict) else {}
            attractions.append(
                Attraction(
                    name=poi.get("name") or "未命名景点",
                    address=poi.get("address") or city,
                    location=location,
                    visit_duration=120,
                    description=poi.get("type") or "高德地图搜索到的真实景点数据",
                    category=poi.get("type") or "景点",
                    rating=_parse_float(biz_ext.get("rating")),
                    image_url=first_photo.get("url"),
                    ticket_price=0,
                )
            )
        return attractions

    def search_hotel(self, city: str, accommodation_type: str) -> Hotel | None:
        if self.use_mock or not self.api_key:
            return None

        type_name = {
            "budget": "经济型酒店",
            "comfort": "舒适型酒店",
            "premium": "高端酒店",
        }.get(accommodation_type, "舒适型酒店")

        pois = self._search_pois(city=city, keywords=f"{city} {type_name}", offset=5)
        if not pois:
            return None

        poi = pois[0]
        location = _parse_location(poi.get("location"))
        biz_ext = poi.get("biz_ext") if isinstance(poi.get("biz_ext"), dict) else {}
        estimated_cost = {"budget": 300, "comfort": 500, "premium": 900}.get(
            accommodation_type,
            500,
        )
        return Hotel(
            name=poi.get("name") or f"{city}{type_name}",
            address=poi.get("address") or city,
            location=location,
            price_range=f"{estimated_cost} 元/晚左右",
            rating=str(biz_ext.get("rating") or ""),
            distance="由高德地图地点搜索返回",
            type=type_name,
            estimated_cost=estimated_cost,
        )

    def build_static_map_url(self, attractions: list[Attraction]) -> str | None:
        if not self.api_key or not attractions:
            return None

        visible_attractions = _unique_attractions(attractions)[:10]
        if not visible_attractions:
            return None

        center = visible_attractions[0].location
        marker_parts = []
        labels = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
        for index, attraction in enumerate(visible_attractions):
            marker_parts.append(
                f"mid,0xFF0000,{labels[index]}:{attraction.location.longitude},{attraction.location.latitude}"
            )

        params = {
            "key": self.api_key,
            "location": f"{center.longitude},{center.latitude}",
            "zoom": "12",
            "size": "750*360",
            "markers": ";".join(marker_parts),
        }
        url = f"{self.base_url}/v3/staticmap?{urlencode(params, safe=';,:')}"
        try:
            response = requests.get(url, timeout=10)
            response.raise_for_status()
        except requests.RequestException:
            return None

        content_type = response.headers.get("content-type", "image/png")
        if not content_type.startswith("image/"):
            return None
        encoded = base64.b64encode(response.content).decode("ascii")
        return f"data:{content_type};base64,{encoded}"

    def _search_pois(self, city: str, keywords: str, offset: int) -> list[dict[str, Any]]:
        response = requests.get(
            f"{self.base_url}/v3/place/text",
            params={
                "key": self.api_key,
                "keywords": keywords,
                "city": city,
                "citylimit": "true",
                "extensions": "all",
                "offset": offset,
                "page": 1,
                "output": "JSON",
            },
            timeout=10,
        )
        response.raise_for_status()
        data = response.json()
        return data.get("pois", [])


def _unique_attractions(attractions: list[Attraction]) -> list[Attraction]:
    seen: set[str] = set()
    unique: list[Attraction] = []
    for attraction in attractions:
        if attraction.name in seen:
            continue
        seen.add(attraction.name)
        unique.append(attraction)
    return unique


def _parse_location(value: Any) -> Location | None:
    if not value or not isinstance(value, str) or "," not in value:
        return None
    longitude, latitude = value.split(",", 1)
    try:
        return Location(longitude=float(longitude), latitude=float(latitude))
    except ValueError:
        return None


def _parse_float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _build_attraction_queries(preferences: str) -> list[str]:
    if "历史" in preferences or "文化" in preferences:
        return ["博物馆", "纪念馆", "历史文化景点", "景点"]
    if "亲子" in preferences:
        return ["亲子景点", "游乐园", "景点"]
    if "美食" in preferences:
        return ["美食街", "特色街区", "景点"]
    if "自然" in preferences or "公园" in preferences:
        return ["公园", "自然景点", "景点"]
    return ["热门景点", "景点"]


@lru_cache
def get_shared_amap_service() -> AmapMCPService:
    return AmapMCPService(
        api_key=settings.amap_api_key,
        use_mock=settings.use_mock_tools,
    )
