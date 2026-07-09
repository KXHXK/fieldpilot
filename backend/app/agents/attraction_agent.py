from app.models import Attraction, Location, TripPlanRequest
from app.services import get_shared_amap_service


class AttractionSearchAgent:
    """Attraction search agent. Uses Amap when mock tools are disabled."""

    def run(self, request: TripPlanRequest) -> list[Attraction]:
        amap_service = get_shared_amap_service()
        real_attractions = amap_service.search_attractions(
            city=request.destination,
            preferences=request.preferences,
        )
        if real_attractions:
            return real_attractions

        city = request.destination
        return [
            Attraction(
                name=f"{city}历史文化核心景点",
                address=f"{city}市中心区域",
                location=Location(longitude=121.4737, latitude=31.2304),
                visit_duration=150,
                description="适合第一次到访，用来快速建立对城市历史文化的整体印象。",
                category="历史文化",
                rating=4.7,
                ticket_price=60,
            ),
            Attraction(
                name=f"{city}轻松漫步街区",
                address=f"{city}特色街区",
                location=Location(longitude=121.49, latitude=31.22),
                visit_duration=90,
                description="适合低强度游览、拍照和用餐，避免行程过赶。",
                category="城市漫步",
                rating=4.5,
                ticket_price=0,
            ),
        ]
