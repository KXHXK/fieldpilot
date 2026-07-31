from __future__ import annotations

import hashlib
import json
from datetime import datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

from app.domain import (
    CandidateBundle,
    LocationInput,
    MealCandidate,
    MealType,
    MissionRead,
    SourceMode,
    StayCandidate,
    TransportCandidate,
    TransportMode,
)
from app.providers.base import ProviderSnapshotData


class FixtureCandidateProvider:
    """Versioned, credential-free candidates for deterministic planner tests."""

    provider_name = "fieldpilot-fixture-v1"

    def __init__(self) -> None:
        self._meal_cache: dict[str, list[MealCandidate]] = {}
        self._meal_traces: list[dict] = []

    def search(self, mission: MissionRead) -> CandidateBundle:
        zone = ZoneInfo(mission.timezone)
        destination_city = mission.visits[0].location.city
        outbound_date = mission.start_date
        return_date = mission.end_date
        outbound = [
            self._intercity(
                "fx-rail-out-safe",
                TransportMode.RAIL,
                "outbound",
                "mission-origin",
                "arrival-hub",
                self._local_datetime(outbound_date, time(6, 30), zone),
                self._local_datetime(outbound_date, time(7, 35), zone),
                73,
                "second_class",
                reliability=94,
            ),
            self._intercity(
                "fx-rail-out-fast",
                TransportMode.RAIL,
                "outbound",
                "mission-origin",
                "arrival-hub",
                self._local_datetime(outbound_date, time(7, 30), zone),
                self._local_datetime(outbound_date, time(8, 30), zone),
                73,
                "second_class",
                reliability=88,
            ),
            self._intercity(
                "fx-rail-out-first",
                TransportMode.RAIL,
                "outbound",
                "mission-origin",
                "arrival-hub",
                self._local_datetime(outbound_date, time(8, 0), zone),
                self._local_datetime(outbound_date, time(9, 0), zone),
                125,
                "first_class",
                reliability=90,
            ),
            self._intercity(
                "fx-flight-out",
                TransportMode.FLIGHT,
                "outbound",
                "mission-origin",
                "arrival-hub",
                self._local_datetime(outbound_date, time(6, 0), zone),
                self._local_datetime(outbound_date, time(8, 50), zone),
                620,
                "economy",
                reliability=72,
            ),
        ]
        returns = [
            self._intercity(
                "fx-rail-return-early",
                TransportMode.RAIL,
                "return",
                "departure-hub",
                "mission-origin",
                self._local_datetime(return_date, time(17, 30), zone),
                self._local_datetime(return_date, time(18, 35), zone),
                73,
                "second_class",
                reliability=90,
            ),
            self._intercity(
                "fx-rail-return-late",
                TransportMode.RAIL,
                "return",
                "departure-hub",
                "mission-origin",
                self._local_datetime(return_date, time(20, 30), zone),
                self._local_datetime(return_date, time(21, 35), zone),
                73,
                "second_class",
                reliability=94,
            ),
            self._intercity(
                "fx-flight-return",
                TransportMode.FLIGHT,
                "return",
                "departure-hub",
                "mission-origin",
                self._local_datetime(return_date, time(19, 0), zone),
                self._local_datetime(return_date, time(21, 10), zone),
                650,
                "economy",
                reliability=75,
            ),
        ]
        stays = [
            StayCandidate(
                candidate_id="fx-hotel-transit",
                provider=self.provider_name,
                source_mode=SourceMode.FIXTURE,
                name=f"{destination_city}交通便利型酒店",
                address=f"{destination_city}目标区域与交通枢纽之间（合成）",
                city=destination_city,
                nightly_price_yuan=380,
                rating=4.2,
            ),
            StayCandidate(
                candidate_id="fx-hotel-near-work",
                provider=self.provider_name,
                source_mode=SourceMode.FIXTURE,
                name=f"{destination_city}工作地点附近酒店",
                address=f"{destination_city}工作地点聚类中心附近（合成）",
                city=destination_city,
                nightly_price_yuan=440,
                rating=4.6,
            ),
            StayCandidate(
                candidate_id="fx-hotel-over-cap",
                provider=self.provider_name,
                source_mode=SourceMode.FIXTURE,
                name=f"{destination_city}超标酒店",
                address=f"{destination_city}中心区域（合成）",
                city=destination_city,
                nightly_price_yuan=560,
                rating=4.8,
            ),
        ]
        first_visit_location = mission.visits[0].location
        last_visit_location = mission.visits[-1].location
        hub_location = first_visit_location.model_copy(
            update={
                "name": f"{destination_city}东站",
                "address": f"{destination_city}东站",
                "longitude": None,
                "latitude": None,
            }
        )
        reference_locations = {
            "mission-origin": mission.origin,
            "arrival-hub": hub_location,
            "departure-hub": hub_location,
            **{visit.task_id: visit.location for visit in mission.visits},
            "hotel:fx-hotel-transit": last_visit_location.model_copy(
                update={"name": stays[0].name}
            ),
            "hotel:fx-hotel-near-work": first_visit_location.model_copy(
                update={"name": stays[1].name}
            ),
            "hotel:fx-hotel-over-cap": first_visit_location.model_copy(
                update={"name": stays[2].name}
            ),
        }
        fingerprint_source = {
            "provider": self.provider_name,
            "origin": mission.origin.model_dump(mode="json"),
            "destination": destination_city,
            "start_date": mission.start_date.isoformat(),
            "end_date": mission.end_date.isoformat(),
            "visits": [
                {
                    "location": visit.location.model_dump(mode="json"),
                    "window_start": visit.window_start.isoformat(),
                    "window_end": visit.window_end.isoformat(),
                    "duration_minutes": visit.duration_minutes,
                }
                for visit in mission.visits
            ],
        }
        fingerprint = hashlib.sha256(
            json.dumps(fingerprint_source, sort_keys=True).encode("utf-8")
        ).hexdigest()
        return CandidateBundle(
            provider=self.provider_name,
            source_mode=SourceMode.FIXTURE,
            fetched_at=datetime.now(timezone.utc),
            query_fingerprint=fingerprint,
            outbound=outbound,
            returns=returns,
            stays=stays,
            reference_locations=reference_locations,
            assumptions=[
                "跨城车次、价格和酒店为冻结 Fixture，不代表实时余票或报价。",
                "Fixture 酒店的路线锚点复用任务地点，仅用于验证跨日规划。",
                "Fixture 只用于验证政策、时窗、排序、修订和失败边界。",
            ],
        )

    async def local_routes(
        self,
        from_ref: str,
        to_ref: str,
        from_location,
        to_location,
        depart_at: datetime,
        preferred_modes: list[str],
        timezone_name: str = "Asia/Shanghai",
    ) -> list[TransportCandidate]:
        route_fingerprint = json.dumps(
            {
                "from": from_location.model_dump(mode="json"),
                "to": to_location.model_dump(mode="json"),
            },
            ensure_ascii=False,
            sort_keys=True,
        )
        seed = int(
            hashlib.sha256(route_fingerprint.encode("utf-8")).hexdigest()[:6],
            16,
        )
        profiles = {
            "transit": (32 + seed % 16, 6, 1, 88),
            "taxi": (20 + seed % 12, 36 + seed % 28, 0, 82),
            "walking": (70 + seed % 30, 0, 0, 96),
            "bicycling": (40 + seed % 20, 4, 0, 84),
        }
        candidates: list[TransportCandidate] = []
        for mode_name in preferred_modes:
            if mode_name not in profiles:
                continue
            duration, price, transfers, reliability = profiles[mode_name]
            mode = TransportMode(mode_name)
            candidate_hash = hashlib.sha1(
                f"{route_fingerprint}:{mode_name}".encode("utf-8")
            ).hexdigest()[:12]
            candidates.append(
                TransportCandidate(
                    candidate_id=f"fx-local-{candidate_hash}",
                    provider=self.provider_name,
                    source_mode=SourceMode.FIXTURE,
                    mode=mode,
                    direction="local",
                    from_ref=from_ref,
                    to_ref=to_ref,
                    depart_at=depart_at,
                    arrive_at=depart_at + timedelta(minutes=duration),
                    price_yuan=price,
                        transfers=transfers,
                        reliability_score=reliability,
                        metadata={
                            "distance_source": "fixture",
                            "from_name": from_location.name,
                            "to_name": to_location.name,
                        },
                    )
                )
        return candidates[:3]

    async def nearby_meals(
        self,
        anchor_ref: str,
        anchor_location: LocationInput,
        meal_type: MealType,
        max_cost_yuan: int,
    ) -> list[MealCandidate]:
        fingerprint_source = {
            "provider": self.provider_name,
            "anchor": anchor_location.model_dump(mode="json"),
            "meal_type": meal_type.value,
            "max_cost_yuan": max_cost_yuan,
        }
        fingerprint = hashlib.sha256(
            json.dumps(
                fingerprint_source,
                ensure_ascii=False,
                sort_keys=True,
            ).encode("utf-8")
        ).hexdigest()
        cache_key = f"{fingerprint}:{anchor_ref}"
        cached = self._meal_cache.get(cache_key)
        if cached is not None:
            return [item.model_copy(deep=True) for item in cached]

        labels = {
            MealType.BREAKFAST: ("早餐", 24),
            MealType.LUNCH: ("午餐", 38),
            MealType.DINNER: ("晚餐", 48),
        }
        label, base_cost = labels[meal_type]
        candidates = [
            MealCandidate(
                candidate_id=(
                    "fx-meal-"
                    + hashlib.sha1(
                        f"{fingerprint}:{index}".encode("utf-8")
                    ).hexdigest()[:12]
                ),
                provider=self.provider_name,
                source_mode=SourceMode.FIXTURE,
                meal_type=meal_type,
                anchor_ref=anchor_ref,
                name=f"{anchor_location.name}附近{label}候选 {index + 1}",
                address=f"{anchor_location.address}周边（合成）",
                estimated_cost_yuan=base_cost + index * 8,
                service_minutes=30 if meal_type != MealType.DINNER else 40,
                distance_meters=220 + index * 180,
                rating=4.3 - index * 0.2,
                metadata={
                    "fixture_version": "meal-fixture-v1",
                    "price_semantics": "人均预算估值",
                },
            )
            for index in range(2)
            if base_cost + index * 8 <= max_cost_yuan
        ]
        self._meal_cache[cache_key] = candidates
        self._meal_traces.append(
            {
                "query_fingerprint": fingerprint,
                "anchor_ref": anchor_ref,
                "meal_type": meal_type.value,
                "max_cost_yuan": max_cost_yuan,
                "source_mode": SourceMode.FIXTURE.value,
                "candidates": [
                    item.model_dump(mode="json") for item in candidates
                ],
            }
        )
        return [item.model_copy(deep=True) for item in candidates]

    def provider_snapshots(self) -> list[ProviderSnapshotData]:
        if not self._meal_traces:
            return []
        fetched_at = datetime.now(timezone.utc)
        return [
            ProviderSnapshotData(
                provider=self.provider_name,
                capability="meal_candidates",
                source_mode=SourceMode.FIXTURE,
                query_fingerprint=hashlib.sha256(
                    json.dumps(
                        [trace["query_fingerprint"] for trace in self._meal_traces],
                        sort_keys=True,
                    ).encode("utf-8")
                ).hexdigest(),
                payload={
                    "provider": self.provider_name,
                    "fixture_version": "meal-fixture-v1",
                    "queries": self._meal_traces,
                    "raw_provider_payload_persisted": False,
                },
                fetched_at=fetched_at,
                expires_at=fetched_at + timedelta(days=30),
            )
        ]

    async def aclose(self) -> None:
        return None

    def _intercity(
        self,
        candidate_id: str,
        mode: TransportMode,
        direction: str,
        from_ref: str,
        to_ref: str,
        depart_at: datetime,
        arrive_at: datetime,
        price_yuan: int,
        cabin_class: str,
        *,
        reliability: int,
    ) -> TransportCandidate:
        return TransportCandidate(
            candidate_id=candidate_id,
            provider=self.provider_name,
            source_mode=SourceMode.FIXTURE,
            mode=mode,
            direction=direction,
            from_ref=from_ref,
            to_ref=to_ref,
            depart_at=depart_at,
            arrive_at=arrive_at,
            price_yuan=price_yuan,
            cabin_class=cabin_class,
            reliability_score=reliability,
        )

    @staticmethod
    def _local_datetime(date_value, time_value: time, zone: ZoneInfo) -> datetime:
        return datetime.combine(date_value, time_value, tzinfo=zone).astimezone(
            timezone.utc
        )
