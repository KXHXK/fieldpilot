from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta, timezone
from typing import Any

from app.domain import (
    CandidateBundle,
    LocationInput,
    MealCandidate,
    MealType,
    MissionRead,
    ReplanEventType,
    SourceMode,
    TransportCandidate,
    TransportMode,
)
from app.providers.base import CandidateProvider, ProviderSnapshotData


class EventAwareCandidateProvider:
    """Apply a typed replan event as a deterministic provider boundary.

    The decorator keeps external adapters unaware of mission execution state while
    ensuring disruption and weather facts affect both intercity candidates and the
    local routes fetched lazily by the planner.
    """

    supported_event_types = {
        ReplanEventType.TRANSPORT_DISRUPTION.value,
        ReplanEventType.WEATHER_RISK.value,
    }

    def __init__(
        self,
        delegate: CandidateProvider,
        *,
        event_id: str,
        event_type: str,
        payload: dict[str, Any],
    ) -> None:
        if event_type not in self.supported_event_types:
            raise ValueError(f"unsupported candidate event: {event_type}")
        self.delegate = delegate
        self.event_id = event_id
        self.event_type = event_type
        self.payload = payload
        self.provider_name = delegate.provider_name
        self._removed_candidate_ids: set[str] = set()
        self._delayed_candidate_ids: set[str] = set()
        self._filtered_modes: set[str] = set()

    def search(self, mission: MissionRead) -> CandidateBundle:
        bundle = self.delegate.search(mission)
        outbound = self._apply_transport_event(bundle.outbound)
        returns = self._apply_transport_event(bundle.returns)
        assumptions = [*bundle.assumptions, self._assumption()]
        return bundle.model_copy(
            update={"outbound": outbound, "returns": returns, "assumptions": assumptions}
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
        routes = await self.delegate.local_routes(
            from_ref,
            to_ref,
            from_location,
            to_location,
            depart_at,
            preferred_modes,
            timezone_name,
        )
        routes = self._apply_transport_event(routes)
        if self.event_type == ReplanEventType.WEATHER_RISK.value:
            routes = self._apply_weather_event(routes, from_ref, to_ref)
        return routes

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
        fingerprint = hashlib.sha256(
            json.dumps(
                {
                    "event_id": self.event_id,
                    "event_type": self.event_type,
                    "payload": self.payload,
                },
                ensure_ascii=False,
                sort_keys=True,
            ).encode("utf-8")
        ).hexdigest()
        return [
            *self.delegate.provider_snapshots(),
            ProviderSnapshotData(
                provider="fieldpilot-event-filter-v1",
                capability="event_candidate_filter",
                source_mode=SourceMode.MANUAL,
                query_fingerprint=fingerprint,
                payload={
                    "event_id": self.event_id,
                    "event_type": self.event_type,
                    "rule": self._assumption(),
                    "removed_candidate_ids": sorted(self._removed_candidate_ids),
                    "delayed_candidate_ids": sorted(self._delayed_candidate_ids),
                    "filtered_modes": sorted(self._filtered_modes),
                },
                fetched_at=datetime.now(timezone.utc),
            ),
        ]

    async def aclose(self) -> None:
        await self.delegate.aclose()

    def _apply_transport_event(
        self, candidates: list[TransportCandidate]
    ) -> list[TransportCandidate]:
        if self.event_type != ReplanEventType.TRANSPORT_DISRUPTION.value:
            return candidates
        target = str(self.payload["candidate_id"])
        status = str(self.payload["status"])
        delay_minutes = int(self.payload.get("estimated_delay_minutes") or 0)
        result: list[TransportCandidate] = []
        for candidate in candidates:
            if candidate.candidate_id != target:
                result.append(candidate)
                continue
            if status in {"cancelled", "unavailable"}:
                self._removed_candidate_ids.add(candidate.candidate_id)
                continue
            delay = timedelta(minutes=delay_minutes)
            metadata = {
                **candidate.metadata,
                "replan_event_id": self.event_id,
                "disruption_status": status,
                "estimated_delay_minutes": delay_minutes,
            }
            self._delayed_candidate_ids.add(candidate.candidate_id)
            result.append(
                candidate.model_copy(
                    update={
                        "depart_at": candidate.depart_at + delay,
                        "arrive_at": candidate.arrive_at + delay,
                        "reliability_score": max(0, candidate.reliability_score - 25),
                        "metadata": metadata,
                    }
                )
            )
        return result

    def _apply_weather_event(
        self,
        candidates: list[TransportCandidate],
        from_ref: str,
        to_ref: str,
    ) -> list[TransportCandidate]:
        affected = set(self.payload.get("affected_task_ids") or [])
        if affected and not ({from_ref, to_ref} & affected):
            return candidates
        severity = str(self.payload["severity"])
        blocked_modes = (
            {TransportMode.WALKING, TransportMode.BICYCLING}
            if severity == "high"
            else {TransportMode.BICYCLING}
        )
        result = []
        for candidate in candidates:
            if candidate.mode in blocked_modes:
                self._removed_candidate_ids.add(candidate.candidate_id)
                self._filtered_modes.add(candidate.mode.value)
                continue
            result.append(candidate)
        return result

    def _assumption(self) -> str:
        if self.event_type == ReplanEventType.TRANSPORT_DISRUPTION.value:
            status = self.payload["status"]
            candidate_id = self.payload["candidate_id"]
            if status == "delayed":
                delay = int(self.payload.get("estimated_delay_minutes") or 0)
                return f"事件 {self.event_id} 将候选 {candidate_id} 延后 {delay} 分钟并降低可靠性。"
            return f"事件 {self.event_id} 从本轮规划排除候选 {candidate_id}（{status}）。"
        severity = self.payload["severity"]
        modes = "步行和骑行" if severity == "high" else "骑行"
        return f"事件 {self.event_id} 对受影响任务过滤{modes}候选（天气风险 {severity}）。"


__all__ = ["EventAwareCandidateProvider"]
