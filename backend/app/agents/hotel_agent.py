from app.models import Hotel, Location, TripPlanRequest
from app.services import get_shared_amap_service


class HotelRecommendAgent:
    """Hotel recommendation agent. Uses Amap when mock tools are disabled."""

    def run(self, request: TripPlanRequest) -> Hotel:
        amap_service = get_shared_amap_service()
        real_hotel = amap_service.search_hotel(
            city=request.destination,
            accommodation_type=request.accommodation_type,
        )
        if real_hotel:
            return real_hotel

        price_map = {
            "budget": ("经济型", 300),
            "comfort": ("舒适型", 500),
            "premium": ("高品质", 900),
        }
        hotel_type, estimated_cost = price_map.get(request.accommodation_type, ("舒适型", 500))

        return Hotel(
            name=f"{request.destination}{hotel_type}酒店",
            address=f"{request.destination}交通便利区域",
            location=Location(longitude=121.48, latitude=31.23),
            price_range=f"{estimated_cost} 元/晚左右",
            rating="4.5",
            distance="距离核心景点约 20 分钟车程",
            type=hotel_type,
            estimated_cost=estimated_cost,
        )
