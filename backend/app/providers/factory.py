from __future__ import annotations

from app.config import Settings
from app.providers.amap import AmapLocalRouteProvider
from app.providers.base import CandidateProvider
from app.providers.fixture import FixtureCandidateProvider


def create_candidate_provider(settings: Settings) -> CandidateProvider:
    fixture = FixtureCandidateProvider()
    if settings.local_route_provider == "fixture":
        return fixture
    return AmapLocalRouteProvider(
        api_key=settings.amap_api_key,
        fallback=fixture,
        base_url=settings.amap_base_url,
        timeout_seconds=settings.provider_timeout_seconds,
        max_retries=settings.provider_max_retries,
        max_concurrency=settings.provider_max_concurrency,
        max_live_calls=settings.provider_max_live_calls,
    )


__all__ = ["create_candidate_provider"]
