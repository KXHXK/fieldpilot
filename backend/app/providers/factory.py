from __future__ import annotations

from app.config import Settings
from app.providers.amap import AmapLocalRouteProvider
from app.providers.base import CandidateProvider
from app.providers.fixture import FixtureCandidateProvider
from app.providers.manual_inventory import ManualInventoryCandidateProvider


def create_candidate_provider(settings: Settings) -> CandidateProvider:
    fixture = FixtureCandidateProvider()
    if settings.local_route_provider == "fixture":
        provider: CandidateProvider = fixture
    else:
        provider = AmapLocalRouteProvider(
            api_key=settings.amap_api_key,
            fallback=fixture,
            base_url=settings.amap_base_url,
            timeout_seconds=settings.provider_timeout_seconds,
            max_retries=settings.provider_max_retries,
            max_concurrency=settings.provider_max_concurrency,
            max_live_calls=settings.provider_max_live_calls,
        )
    if settings.manual_candidate_file:
        return ManualInventoryCandidateProvider(provider, settings.manual_candidate_file)
    return provider


__all__ = ["create_candidate_provider"]
