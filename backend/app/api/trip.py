from fastapi import APIRouter

from app.agents import TripPlannerAgent
from app.models import TripPlan, TripPlanRequest
from app.services import get_shared_amap_service, get_unsplash_service


router = APIRouter(prefix="/trip", tags=["trip"])


@router.post("/plan", response_model=TripPlan)
async def create_trip_plan(request: TripPlanRequest) -> TripPlan:
    """
    Create a trip plan.

    Chapter 13.3 introduces the multi-agent workflow.
    Chapter 13.4 enriches attractions with image URLs through a service wrapper.
    """
    planner = TripPlannerAgent()
    trip_plan = planner.run(request)

    unsplash_service = get_unsplash_service()
    for day in trip_plan.days:
        for attraction in day.attractions:
            if attraction.image_url:
                continue
            attraction.image_url = unsplash_service.get_attraction_photo_url(
                city=trip_plan.city,
                category=attraction.category,
            )

    all_attractions = [
        attraction
        for day in trip_plan.days
        for attraction in day.attractions
    ]
    trip_plan.map_image_url = get_shared_amap_service().build_static_map_url(all_attractions)

    return trip_plan
