import asyncio
import logging
from time import perf_counter

from fastapi import APIRouter

from app.agents import TripPlannerAgent
from app.models import TripPlan, TripPlanRequest
from app.services import get_shared_amap_service, get_unsplash_service


router = APIRouter(prefix="/trip", tags=["trip"])
logger = logging.getLogger(__name__)


@router.post("/plan", response_model=TripPlan)
async def create_trip_plan(request: TripPlanRequest) -> TripPlan:
    """
    Create a trip plan.

    Chapter 13.3 introduces the multi-agent workflow.
    Chapter 13.4 enriches attractions with image URLs through a service wrapper.
    """
    started_at = perf_counter()
    logger.info("Trip planning started: city=%s, dates=%s to %s", request.destination, request.start_date, request.end_date)

    planner = TripPlannerAgent()
    trip_plan = planner.run(request)

    unsplash_service = get_unsplash_service()
    attractions_without_images = [
        attraction
        for day in trip_plan.days
        for attraction in day.attractions
        if not attraction.image_url
    ]
    image_urls = await asyncio.gather(
        *(
            asyncio.to_thread(
                unsplash_service.get_attraction_photo_url,
                city=trip_plan.city,
                attraction_name=attraction.name,
                category=attraction.category,
            )
            for attraction in attractions_without_images
        )
    )
    for attraction, image_url in zip(attractions_without_images, image_urls):
        attraction.image_url = image_url

    all_attractions = [
        attraction
        for day in trip_plan.days
        for attraction in day.attractions
    ]
    trip_plan.map_image_url = get_shared_amap_service().build_static_map_url(all_attractions)
    logger.info("Trip planning completed in %.1fs", perf_counter() - started_at)

    return trip_plan
