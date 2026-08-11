from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from pathlib import Path

from pydantic import Field, model_validator

from app.domain import (
    CandidateBundle,
    LocationInput,
    MealCandidate,
    MealType,
    MissionRead,
    SourceMode,
    StayCandidate,
    TransportCandidate,
)
from app.domain.mission import StrictModel
from app.providers.base import CandidateProvider, ProviderSnapshotData


class ManualInventoryImport(StrictModel):
    import_id: str = Field(min_length=8, max_length=120)
    source_label: str = Field(min_length=1, max_length=120)
    outbound: list[TransportCandidate] = Field(min_length=1, max_length=50)
    returns: list[TransportCandidate] = Field(min_length=1, max_length=50)
    stays: list[StayCandidate] = Field(default_factory=list, max_length=50)
    notes: str = Field(default="", max_length=500)

    @model_validator(mode="after")
    def validate_directions(self) -> ManualInventoryImport:
        if any(item.direction != "outbound" for item in self.outbound):
            raise ValueError("outbound 候选的 direction 必须为 outbound")
        if any(item.direction != "return" for item in self.returns):
            raise ValueError("returns 候选的 direction 必须为 return")
        return self


class ManualInventoryCandidateProvider:
    """Overlay authorized rail/flight/hotel candidates on a local-route provider."""

    def __init__(self, delegate: CandidateProvider, import_file: str) -> None:
        self.delegate = delegate
        self.import_path = Path(import_file).expanduser().resolve()
        self.provider_name = f"manual-inventory+{delegate.provider_name}"
        self._snapshot: ProviderSnapshotData | None = None

    def search(self, mission: MissionRead) -> CandidateBundle:
        raw = self.import_path.read_bytes()
        imported = ManualInventoryImport.model_validate_json(raw)
        base = self.delegate.search(mission)
        provider = f"manual:{imported.source_label}"
        outbound = [self._manual_transport(item, provider) for item in imported.outbound]
        returns = [self._manual_transport(item, provider) for item in imported.returns]
        stays = [self._manual_stay(item, provider) for item in imported.stays]
        reference_locations = {
            **base.reference_locations,
            **{
                f"hotel:{stay.candidate_id}": LocationInput(
                    name=stay.name,
                    address=stay.address,
                    city=stay.city,
                )
                for stay in stays
            },
        }
        fingerprint = hashlib.sha256(raw).hexdigest()
        self._snapshot = ProviderSnapshotData(
            provider=provider,
            capability="manual_intercity_and_stay_inventory",
            source_mode=SourceMode.MANUAL,
            query_fingerprint=fingerprint,
            payload={
                "import_id": imported.import_id,
                "source_label": imported.source_label,
                "outbound_count": len(outbound),
                "return_count": len(returns),
                "stay_count": len(stays),
                "notes": imported.notes,
                "content_sha256": fingerprint,
            },
            fetched_at=datetime.now(timezone.utc),
        )
        return base.model_copy(
            update={
                "provider": self.provider_name,
                "source_mode": SourceMode.MIXED,
                "query_fingerprint": hashlib.sha256(
                    f"{base.query_fingerprint}:{fingerprint}".encode("utf-8")
                ).hexdigest(),
                "outbound": outbound,
                "returns": returns,
                "stays": stays,
                "reference_locations": reference_locations,
                "assumptions": [
                    *base.assumptions,
                    f"跨城交通和住宿来自人工导入 {imported.import_id}，来源标记为 manual。",
                ],
            }
        )

    async def local_routes(
        self,
        from_ref: str,
        to_ref: str,
        from_location: LocationInput,
        to_location: LocationInput,
        depart_at: datetime,
        preferred_modes: list[str],
        timezone_name: str = "Asia/Shanghai",
    ) -> list[TransportCandidate]:
        return await self.delegate.local_routes(
            from_ref,
            to_ref,
            from_location,
            to_location,
            depart_at,
            preferred_modes,
            timezone_name,
        )

    async def nearby_meals(
        self,
        anchor_ref: str,
        anchor_location: LocationInput,
        meal_type: MealType,
        max_cost_yuan: int,
    ) -> list[MealCandidate]:
        return await self.delegate.nearby_meals(
            anchor_ref, anchor_location, meal_type, max_cost_yuan
        )

    def provider_snapshots(self) -> list[ProviderSnapshotData]:
        snapshots = self.delegate.provider_snapshots()
        return [*snapshots, *([self._snapshot] if self._snapshot is not None else [])]

    async def aclose(self) -> None:
        await self.delegate.aclose()

    @staticmethod
    def _manual_transport(
        candidate: TransportCandidate, provider: str
    ) -> TransportCandidate:
        return candidate.model_copy(
            update={"provider": provider, "source_mode": SourceMode.MANUAL}
        )

    @staticmethod
    def _manual_stay(candidate: StayCandidate, provider: str) -> StayCandidate:
        return candidate.model_copy(
            update={"provider": provider, "source_mode": SourceMode.MANUAL}
        )


__all__ = ["ManualInventoryCandidateProvider", "ManualInventoryImport"]
