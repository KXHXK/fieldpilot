from datetime import date

from app.agents.attraction_agent import AttractionSearchAgent
from app.agents.hotel_agent import HotelRecommendAgent
from app.agents.planner_agent import ItineraryPlanAgent
from app.agents.weather_agent import WeatherQueryAgent
from app.models import Budget, TripPlan, TripPlanRequest
from app.services import LLMService, get_shared_amap_service


class TripPlannerAgent:
    """Coordinator for the chapter 13 multi-agent workflow."""

    def __init__(self):
        self.amap_service = get_shared_amap_service()
        self.weather_agent = WeatherQueryAgent()
        self.attraction_agent = AttractionSearchAgent()
        self.hotel_agent = HotelRecommendAgent()
        self.itinerary_agent = ItineraryPlanAgent()
        self.llm_service = LLMService()

    def run(self, request: TripPlanRequest) -> TripPlan:
        weather_info = self.weather_agent.run(request)
        attractions = self.attraction_agent.run(request)
        hotel = self.hotel_agent.run(request)
        day_plans = self.itinerary_agent.run(
            request=request,
            attractions=attractions,
            weather_info=weather_info,
            hotel=hotel,
        )
        budget = self._calculate_budget(request, day_plans, hotel)
        overall_suggestions = self.llm_service.generate_overall_suggestions(
            request=request,
            weather_info=weather_info,
            attractions=attractions,
            hotel=hotel,
        )

        return TripPlan(
            city=request.destination,
            start_date=request.start_date,
            end_date=request.end_date,
            days=day_plans,
            weather_info=weather_info,
            overall_suggestions=overall_suggestions,
            budget=budget,
        )

    def _calculate_budget(self, request: TripPlanRequest, day_plans, hotel) -> Budget:
        total_days = max(
            (
                _parse_date_or_today(request.end_date)
                - _parse_date_or_today(request.start_date)
            ).days
            + 1,
            1,
        )
        user_budget = request.budget or 0
        if user_budget > 0:
            total_attractions = round(user_budget * 0.15)
            total_hotels = round(user_budget * 0.45)
            total_meals = round(user_budget * 0.25)
            total_transportation = user_budget - total_attractions - total_hotels - total_meals
        else:
            total_attractions = sum(
                attraction.ticket_price
                for day in day_plans
                for attraction in day.attractions
            )
            total_meals = sum(meal.estimated_cost for day in day_plans for meal in day.meals)
            total_hotels = hotel.estimated_cost * max(total_days - 1, 1)
            total_transportation = 100 * total_days

        return Budget(
            total_attractions=total_attractions,
            total_hotels=total_hotels,
            total_meals=total_meals,
            total_transportation=total_transportation,
            total=total_attractions + total_hotels + total_meals + total_transportation,
        )


def _parse_date_or_today(value: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError:
        return date.today()
