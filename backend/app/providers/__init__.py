from app.providers.amap import AmapLocalRouteProvider, ProviderFailure
from app.providers.base import CandidateProvider, ProviderSnapshotData
from app.providers.event_aware import EventAwareCandidateProvider
from app.providers.factory import create_candidate_provider
from app.providers.fixture import FixtureCandidateProvider
from app.providers.manual_inventory import (
    ManualInventoryCandidateProvider,
    ManualInventoryImport,
)

__all__ = [
    "AmapLocalRouteProvider",
    "CandidateProvider",
    "EventAwareCandidateProvider",
    "FixtureCandidateProvider",
    "ManualInventoryCandidateProvider",
    "ManualInventoryImport",
    "ProviderFailure",
    "ProviderSnapshotData",
    "create_candidate_provider",
]
