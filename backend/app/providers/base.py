from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Protocol

from app.domain import CandidateBundle, LocationInput, MissionRead, SourceMode, TransportCandidate


@dataclass(frozen=True)
class ProviderSnapshotData:
    provider: str
    capability: str
    source_mode: SourceMode
    query_fingerprint: str
    payload: dict[str, Any]
    fetched_at: datetime
    expires_at: datetime | None = None


class CandidateProvider(Protocol):
    provider_name: str

    def search(self, mission: MissionRead) -> CandidateBundle: ...

    async def local_routes(
        self,
        from_ref: str,
        to_ref: str,
        from_location: LocationInput,
        to_location: LocationInput,
        depart_at: datetime,
        preferred_modes: list[str],
        timezone_name: str = "Asia/Shanghai",
    ) -> list[TransportCandidate]: ...

    def provider_snapshots(self) -> list[ProviderSnapshotData]: ...

    async def aclose(self) -> None: ...


__all__ = ["CandidateProvider", "ProviderSnapshotData"]
