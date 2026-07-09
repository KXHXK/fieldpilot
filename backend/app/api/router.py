from fastapi import APIRouter

from app.api import health, trip


api_router = APIRouter()
api_router.include_router(health.router, tags=["health"])
api_router.include_router(trip.router)
