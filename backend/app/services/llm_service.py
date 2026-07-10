import logging

from openai import OpenAI

from app.config import settings
from app.models import Attraction, Hotel, TripPlanRequest, WeatherInfo


logger = logging.getLogger(__name__)


class LLMService:
    """OpenAI-compatible LLM service. Moonshot Kimi works with this client."""

    def __init__(self):
        self.use_mock = settings.use_mock_llm
        self.model = settings.model_name
        self.client: OpenAI | None = None
        if not self.use_mock and settings.openai_api_key:
            self.client = OpenAI(
                api_key=settings.openai_api_key,
                base_url=settings.openai_base_url,
                timeout=15,
                max_retries=0,
            )

    def generate_overall_suggestions(
        self,
        request: TripPlanRequest,
        weather_info: list[WeatherInfo],
        attractions: list[Attraction],
        hotel: Hotel,
    ) -> str:
        if self.use_mock:
            return (
                "当前为 Mock LLM 结果。行程已根据天气、景点和酒店信息生成；"
                "关闭 USE_MOCK_LLM 后将由 Kimi 生成更自然的总结建议。"
            )

        if not self.client:
            logger.warning("Kimi is not configured; returning a non-LLM trip summary.")
            return "已根据天气、景点与酒店搜索结果生成行程。Kimi 总结暂不可用，请检查 OPENAI_API_KEY。"

        weather_text = "\n".join(
            f"- {item.date}: 白天{item.day_weather}{item.day_temp}℃，夜间{item.night_weather}{item.night_temp}℃"
            for item in weather_info
        )
        attraction_text = "\n".join(
            f"- {item.name}: {item.address}，{item.description}"
            for item in attractions[:8]
        )

        prompt = f"""
请基于真实工具返回的数据，为用户生成一段简洁的旅行总建议。

用户需求：
- 目的地：{request.destination}
- 日期：{request.start_date} 至 {request.end_date}
- 偏好：{request.preferences}
- 预算：{request.budget} 元
- 交通：{request.transport_type}
- 住宿：{request.accommodation_type}

天气数据：
{weather_text}

景点数据：
{attraction_text}

酒店数据：
- {hotel.name}: {hotel.address}，{hotel.price_range}

要求：
1. 只用中文。
2. 不要编造不存在的数据。
3. 说明哪些建议来自实时天气、地图搜索和酒店搜索。
4. 控制在 180 字以内。
"""

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "你是一个谨慎、实用的旅行规划助手。"},
                    {"role": "user", "content": prompt},
                ],
                temperature=1,
            )
            return response.choices[0].message.content or ""
        except Exception as exc:
            logger.warning("Kimi summary request failed: error_type=%s", type(exc).__name__)
            return "已根据天气、景点与酒店搜索结果生成行程。Kimi 总结暂不可用，建议稍后重试。"
