from datetime import date, timedelta

from app.models import TripPlanRequest, WeatherInfo
from app.services import TavilyWeatherService


class WeatherQueryAgent:
    """Weather query agent. Uses Tavily when mock tools are disabled."""

    def run(self, request: TripPlanRequest) -> list[WeatherInfo]:
        dates = _date_range(request.start_date, request.end_date)
        try:
            tavily_weather = TavilyWeatherService().get_weather(request.destination, dates)
        except Exception:
            tavily_weather = []
        if tavily_weather:
            return tavily_weather

        return [
            WeatherInfo(
                date=current,
                day_weather="多云",
                night_weather="晴",
                day_temp=26,
                night_temp=18,
                wind_direction="东风",
                wind_power="3级",
            )
            for current in dates
        ]


def _date_range(start_value: str, end_value: str) -> list[str]:
    start = _parse_date_or_today(start_value)
    total_days = max((_parse_date_or_today(end_value) - start).days + 1, 1)
    return [(start + timedelta(days=index)).isoformat() for index in range(total_days)]


def _parse_date_or_today(value: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError:
        return date.today()
