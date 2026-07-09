from typing import Literal

from pydantic import BaseModel, Field, field_validator


class Location(BaseModel):
    """经纬度坐标。"""

    longitude: float = Field(..., description="经度", ge=-180, le=180)
    latitude: float = Field(..., description="纬度", ge=-90, le=90)


class Attraction(BaseModel):
    """景点信息。"""

    name: str = Field(..., description="景点名称")
    address: str = Field(..., description="地址")
    location: Location = Field(..., description="经纬度坐标")
    visit_duration: int = Field(..., description="建议游览时间，单位分钟", gt=0)
    description: str = Field(..., description="景点描述")
    category: str | None = Field(default="景点", description="景点类别")
    rating: float | None = Field(default=None, description="评分", ge=0, le=5)
    image_url: str | None = Field(default=None, description="图片 URL")
    ticket_price: int = Field(default=0, description="门票价格，单位元", ge=0)


class Meal(BaseModel):
    """餐饮信息。"""

    type: Literal["breakfast", "lunch", "dinner", "snack"] = Field(..., description="餐饮类型")
    name: str = Field(..., description="餐饮名称")
    address: str | None = Field(default=None, description="地址")
    location: Location | None = Field(default=None, description="经纬度坐标")
    description: str | None = Field(default=None, description="描述")
    estimated_cost: int = Field(default=0, description="预计费用，单位元", ge=0)


class Hotel(BaseModel):
    """酒店信息。"""

    name: str = Field(..., description="酒店名称")
    address: str = Field(default="", description="酒店地址")
    location: Location | None = Field(default=None, description="酒店位置")
    price_range: str = Field(default="", description="价格范围")
    rating: str = Field(default="", description="评分")
    distance: str = Field(default="", description="距离说明")
    type: str = Field(default="", description="酒店类型")
    estimated_cost: int = Field(default=0, description="预计每晚费用，单位元", ge=0)


class Budget(BaseModel):
    """预算信息。"""

    total_attractions: int = Field(default=0, description="景点门票总费用", ge=0)
    total_hotels: int = Field(default=0, description="酒店总费用", ge=0)
    total_meals: int = Field(default=0, description="餐饮总费用", ge=0)
    total_transportation: int = Field(default=0, description="交通总费用", ge=0)
    total: int = Field(default=0, description="总费用", ge=0)


class DayPlan(BaseModel):
    """单日行程。"""

    date: str = Field(..., description="日期")
    day_index: int = Field(..., description="第几天，从 1 开始", ge=1)
    description: str = Field(..., description="当日行程描述")
    transportation: str = Field(..., description="交通建议")
    accommodation: str = Field(..., description="住宿建议")
    hotel: Hotel | None = Field(default=None, description="酒店信息")
    attractions: list[Attraction] = Field(default_factory=list, description="景点列表")
    meals: list[Meal] = Field(default_factory=list, description="餐饮安排")


class WeatherInfo(BaseModel):
    """天气信息。"""

    date: str = Field(..., description="日期")
    day_weather: str = Field(..., description="白天天气")
    night_weather: str = Field(..., description="夜间天气")
    day_temp: int = Field(..., description="白天温度，单位摄氏度")
    night_temp: int = Field(..., description="夜间温度，单位摄氏度")
    wind_direction: str = Field(..., description="风向")
    wind_power: str = Field(..., description="风力")

    @field_validator("day_temp", "night_temp", mode="before")
    @classmethod
    def parse_temperature(cls, value):
        if isinstance(value, str):
            cleaned = (
                value.replace("°C", "")
                .replace("℃", "")
                .replace("度", "")
                .replace("°", "")
                .strip()
            )
            try:
                return int(cleaned)
            except ValueError:
                return 0
        return value


class TripPlan(BaseModel):
    """完整旅行计划。"""

    city: str = Field(..., description="目的地城市")
    start_date: str = Field(..., description="开始日期")
    end_date: str = Field(..., description="结束日期")
    days: list[DayPlan] = Field(default_factory=list, description="每日行程")
    weather_info: list[WeatherInfo] = Field(default_factory=list, description="天气信息")
    overall_suggestions: str = Field(..., description="总体建议")
    budget: Budget | None = Field(default=None, description="预算信息")
    map_image_url: str | None = Field(default=None, description="高德静态地图 URL")


class TripPlanRequest(BaseModel):
    """前端表单提交的旅行规划请求。"""

    destination: str = Field(..., description="目的地城市", min_length=1)
    start_date: str = Field(..., description="开始日期")
    end_date: str = Field(..., description="结束日期")
    preferences: str = Field(default="", description="用户旅行偏好")
    budget: int = Field(default=0, description="用户预算，单位元", ge=0)
    transport_type: Literal["public_transport", "taxi", "walking"] = Field(
        default="public_transport",
        description="偏好的交通方式",
    )
    accommodation_type: Literal["budget", "comfort", "premium"] = Field(
        default="comfort",
        description="偏好的住宿类型",
    )
