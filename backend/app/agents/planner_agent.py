from datetime import date, timedelta

from app.models import Attraction, DayPlan, Hotel, Meal, TripPlanRequest, WeatherInfo


class ItineraryPlanAgent:
    """Itinerary planning agent. Builds daily plans from real tool results."""

    def run(
        self,
        request: TripPlanRequest,
        attractions: list[Attraction],
        weather_info: list[WeatherInfo],
        hotel: Hotel,
    ) -> list[DayPlan]:
        start = _parse_date_or_today(request.start_date)
        total_days = max((_parse_date_or_today(request.end_date) - start).days + 1, 1)
        unique_attractions = _unique_attractions(attractions)
        attractions_per_day = 2 if len(unique_attractions) >= total_days * 2 else 1

        plans: list[DayPlan] = []
        used_count = 0
        for index in range(total_days):
            current = start + timedelta(days=index)
            day_attractions = unique_attractions[used_count : used_count + attractions_per_day]
            used_count += attractions_per_day

            weather = weather_info[min(index, len(weather_info) - 1)] if weather_info else None
            attraction_names = "、".join(item.name for item in day_attractions) or "酒店周边街区与自由活动"

            plans.append(
                DayPlan(
                    date=current.isoformat(),
                    day_index=index + 1,
                    description=_build_day_description(
                        day_index=index,
                        city=request.destination,
                        weather=weather,
                        attraction_names=attraction_names,
                    ),
                    transportation=_build_transportation(
                        transport_type=request.transport_type,
                        weather=weather,
                        day_index=index,
                    ),
                    accommodation=_build_accommodation(
                        hotel=hotel,
                        day_index=index,
                        total_days=total_days,
                    ),
                    hotel=hotel,
                    attractions=day_attractions,
                    meals=[
                        Meal(
                            type="lunch",
                            name=_meal_name(request.destination, index),
                            description=_meal_description(index),
                            estimated_cost=80 + index * 20,
                        )
                    ],
                )
            )
        return plans


def _build_day_description(
    day_index: int,
    city: str,
    weather: WeatherInfo | None,
    attraction_names: str,
) -> str:
    themes = [
        "先从城市核心文化地标入手。",
        "把节奏放慢，集中参观更有信息量的场馆。",
        "留出弹性时间，把未尽兴的区域补上。",
        "选择轻量路线，避免最后一天过度奔波。",
        "围绕交通便利区域做半日延展。",
    ]
    openings = [
        f"第 {day_index + 1} 天建议安排 {attraction_names}，先建立对 {city} 的整体印象。",
        f"第 {day_index + 1} 天可以围绕 {attraction_names} 深入展开，减少跨区移动。",
        f"第 {day_index + 1} 天把 {attraction_names} 放在较轻松的时段，给休息和临时调整留余地。",
        f"第 {day_index + 1} 天以 {attraction_names} 为主，路线保持短距离串联。",
        f"第 {day_index + 1} 天安排 {attraction_names}，适合作为行程的补充和收尾。",
    ]
    weather_text = _weather_sentence(weather, day_index)
    return f"{openings[day_index % len(openings)]}{weather_text}{themes[day_index % len(themes)]}"


def _weather_sentence(weather: WeatherInfo | None, day_index: int) -> str:
    if not weather or weather.day_weather == "暂无天气":
        return "天气数据暂不稳定，建议当天早上再确认一次预报。"
    if any(word in weather.day_weather for word in ["雨", "雷", "雪"]):
        rainy_sentences = [
            f"当天有{weather.day_weather}，气温约 {weather.day_temp}℃，更适合把室内场馆放在前半天。",
            f"{weather.day_weather}会影响露天停留，建议把户外步行压缩到两段短距离。",
            f"考虑到{weather.day_weather}和 {weather.day_temp}℃ 左右的体感，行程中间安排一段室内休整。",
        ]
        return rainy_sentences[day_index % len(rainy_sentences)]
    fair_sentences = [
        f"天气为{weather.day_weather}，约 {weather.day_temp}℃，适合穿插一段街区步行。",
        f"{weather.day_weather}天气比较利于移动，可以把两个景点安排在同一半天完成。",
        f"当天气温约 {weather.day_temp}℃，建议上午出发，下午保留咖啡或简餐休息。",
    ]
    return fair_sentences[day_index % len(fair_sentences)]


def _build_transportation(transport_type: str, weather: WeatherInfo | None, day_index: int) -> str:
    is_rainy = bool(weather and any(word in weather.day_weather for word in ["雨", "雷", "雪"]))
    if transport_type == "taxi":
        choices = [
            "上午直接打车到首个景点，下午按实际体力选择短途打车或地铁。",
            "景点之间以网约车衔接，避开换乘复杂的路线。",
            "返程日提前约车，行李寄存后再安排一个近距离景点。",
            "晚间如继续活动，优先打车回酒店，减少夜间步行。",
        ]
    elif transport_type == "walking":
        choices = [
            "选择相邻景点步行串联，单段步行尽量控制在 20 分钟以内。",
            "上午步行看街区，下午用地铁补足较远距离。",
            "把酒店周边和交通枢纽附近作为主要活动范围。",
            "步行路线以阴凉街区和室内停留点穿插安排。",
        ]
    else:
        choices = [
            "以地铁到达核心区域，出站后步行前往景点。",
            "用地铁串联主要景点，晚间根据天气决定是否短途打车。",
            "返程日优先选择地铁或机场线，景点安排靠近交通节点。",
            "跨区移动尽量放在非高峰时段，减少排队和换乘时间。",
        ]
    suggestion = choices[day_index % len(choices)]
    if is_rainy:
        suggestion += " 当天有降水，建议把露天步行压缩到必要路段。"
    return suggestion


def _build_accommodation(hotel: Hotel, day_index: int, total_days: int) -> str:
    choices = [
        f"抵达后先到 {hotel.name} 放下行李，再开始轻量游览。",
        f"继续住在 {hotel.name}，把换酒店的时间留给参观和休息。",
        f"可在 {hotel.name} 寄存行李，下午按返程时间灵活收尾。",
        f"若当天活动结束较晚，建议直接回 {hotel.name} 休息，不再追加夜间远距离行程。",
    ]
    if total_days <= 1:
        return f"当天不强制安排住宿；如需过夜，可选择 {hotel.name}。"
    if day_index == total_days - 1:
        return choices[2]
    return choices[day_index % len(choices)]


def _meal_name(city: str, day_index: int) -> str:
    names = [
        f"{city}本地特色午餐",
        f"{city}老字号简餐",
        f"{city}轻松收尾餐",
        f"{city}街区小馆",
    ]
    return names[day_index % len(names)]


def _meal_description(day_index: int) -> str:
    descriptions = [
        "安排在首个景点附近，减少抵达当天的额外移动。",
        "选择博物馆或历史街区周边餐厅，方便下午继续参观。",
        "选择交通便利区域用餐，给返程或晚间活动留出余量。",
        "优先选择不需要排长队的餐厅，避免压缩参观时间。",
    ]
    return descriptions[day_index % len(descriptions)]


def _unique_attractions(attractions: list[Attraction]) -> list[Attraction]:
    seen: set[str] = set()
    unique: list[Attraction] = []
    for attraction in attractions:
        if attraction.name in seen:
            continue
        seen.add(attraction.name)
        unique.append(attraction)
    return unique


def _parse_date_or_today(value: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError:
        return date.today()
