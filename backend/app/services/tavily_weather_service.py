import re
from concurrent.futures import ThreadPoolExecutor

from tavily import TavilyClient

from app.config import settings
from app.models import WeatherInfo


class TavilyWeatherService:
    """Weather search service backed by Tavily."""

    def __init__(self):
        self.api_key = settings.tavily_api_key
        self.use_mock = settings.use_mock_tools
        self.client = TavilyClient(api_key=self.api_key) if self.api_key else None

    def get_weather(self, city: str, dates: list[str]) -> list[WeatherInfo]:
        if self.use_mock or not self.client:
            return []

        # Each date needs an independent real-time search, but running them
        # serially makes a multi-day request exceed the cloud gateway timeout.
        worker_count = min(len(dates), 3)
        with ThreadPoolExecutor(max_workers=worker_count) as executor:
            return list(executor.map(lambda date_value: self._get_weather_item(city, date_value), dates))

    def _get_weather_item(self, city: str, date_value: str) -> WeatherInfo:
        query = (
            f"{city} {date_value} 天气预报，白天天气、夜间天气、"
            "最高温、最低温、风向、风力"
        )
        return _weather_from_answer(date_value, self._safe_search(query))

    def _safe_search(self, query: str) -> str:
        if not self.client:
            return ""

        try:
            response = self.client.search(
                query=query,
                search_depth="basic",
                include_answer=True,
                max_results=3,
                timeout=8,
            )
            return response.get("answer") or _join_result_content(response)
        except Exception:
            return ""


def _join_result_content(response: dict) -> str:
    results = response.get("results", [])
    return "\n".join(result.get("content", "") for result in results)


def _weather_from_answer(date_value: str, answer: str) -> WeatherInfo:
    if not answer:
        return WeatherInfo(
            date=date_value,
            day_weather="暂无天气",
            night_weather="暂无天气",
            day_temp=0,
            night_temp=0,
            wind_direction="暂无风向",
            wind_power="暂无风力",
        )

    temperatures = [
        int(value)
        for value in re.findall(
            r"(-?\d{1,2})\s*(?:°C|℃|度|degrees Celsius)",
            answer,
            re.IGNORECASE,
        )
    ]
    day_temp = max(temperatures) if temperatures else 0
    night_temp = min(temperatures) if temperatures else 0
    weather_label = _pick_weather_label(answer)

    return WeatherInfo(
        date=date_value,
        day_weather=weather_label,
        night_weather=weather_label,
        day_temp=day_temp,
        night_temp=night_temp,
        wind_direction=_pick_wind_direction(answer),
        wind_power=_pick_wind_power(answer),
    )


def _pick_weather_label(answer: str) -> str:
    for label in ["暴雨", "大雨", "中雨", "小雨", "阵雨", "雷阵雨", "阴", "多云", "晴", "雪"]:
        if label in answer:
            return label

    lower_answer = answer.lower()
    english_labels = [
        ("thunder", "雷阵雨"),
        ("storm", "暴雨"),
        ("shower", "阵雨"),
        ("rain", "小雨"),
        ("cloud", "多云"),
        ("overcast", "阴"),
        ("sunny", "晴"),
        ("clear", "晴"),
        ("snow", "雪"),
    ]
    for keyword, label in english_labels:
        if keyword in lower_answer:
            return label
    return "暂无天气摘要"


def _pick_wind_direction(answer: str) -> str:
    match = re.search(r"([东南西北东北东南西北西南]+风)", answer)
    if match:
        return match.group(1)

    lower_answer = answer.lower()
    if "north" in lower_answer:
        return "北风"
    if "south" in lower_answer:
        return "南风"
    if "east" in lower_answer:
        return "东风"
    if "west" in lower_answer:
        return "西风"
    return "暂无风向"


def _pick_wind_power(answer: str) -> str:
    match = re.search(r"(\d\s*[-到至]?\s*\d?\s*级)", answer)
    if match:
        return match.group(1).replace(" ", "")
    match = re.search(r"(\d{1,2})\s*(?:km/h|公里/小时)", answer, re.IGNORECASE)
    if match:
        return f"{match.group(1)} km/h"
    return "暂无风力"
