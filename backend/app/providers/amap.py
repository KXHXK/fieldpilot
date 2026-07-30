from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import math
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from time import perf_counter
from typing import Any
from zoneinfo import ZoneInfo

import httpx

from app.domain import (
    CandidateBundle,
    LocationInput,
    MissionRead,
    SourceMode,
    TransportCandidate,
    TransportMode,
)
from app.providers.base import ProviderSnapshotData
from app.providers.fixture import FixtureCandidateProvider

logger = logging.getLogger(__name__)


class ProviderFailure(RuntimeError):
    def __init__(
        self,
        failure_type: str,
        *,
        status_code: int | None = None,
    ) -> None:
        self.failure_type = failure_type
        self.status_code = status_code
        super().__init__(failure_type)


@dataclass(frozen=True)
class _ResolvedPoint:
    longitude: float
    latitude: float
    citycode: str | None

    @property
    def coordinates(self) -> str:
        return f"{self.longitude:.6f},{self.latitude:.6f}"


class AmapLocalRouteProvider:
    """Amap v5 local routes with bounded I/O and per-query Fixture fallback."""

    provider_name = "amap-webservice-v5"
    _supported_modes = {"transit", "taxi", "walking", "bicycling"}

    def __init__(
        self,
        *,
        api_key: str,
        fallback: FixtureCandidateProvider | None = None,
        base_url: str = "https://restapi.amap.com",
        timeout_seconds: float = 3.0,
        max_retries: int = 1,
        max_concurrency: int = 4,
        max_live_calls: int = 32,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self.api_key = api_key
        self.fallback = fallback or FixtureCandidateProvider()
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds
        self.max_retries = max_retries
        self.max_live_calls = max_live_calls
        self._client = client or httpx.AsyncClient(base_url=self.base_url)
        self._owns_client = client is None
        self._semaphore = asyncio.Semaphore(max_concurrency)
        self._budget_lock = asyncio.Lock()
        self._cache_lock = asyncio.Lock()
        self._live_calls = 0
        self._route_cache: dict[str, list[TransportCandidate]] = {}
        self._route_inflight: dict[str, asyncio.Task[list[TransportCandidate]]] = {}
        self._point_cache: dict[str, _ResolvedPoint] = {}
        self._point_inflight: dict[str, asyncio.Task[_ResolvedPoint]] = {}
        self._route_traces: list[dict[str, Any]] = []
        self._http_events: list[dict[str, Any]] = []

    def search(self, mission: MissionRead) -> CandidateBundle:
        return self.fallback.search(mission)

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
        modes = list(
            dict.fromkeys(mode for mode in preferred_modes if mode in self._supported_modes)
        )
        fingerprint = self._fingerprint(
            {
                "from_ref": from_ref,
                "to_ref": to_ref,
                "depart_at": depart_at.replace(second=0, microsecond=0).isoformat(),
                "modes": modes,
                "timezone": timezone_name,
            }
        )
        async with self._cache_lock:
            cached = self._route_cache.get(fingerprint)
            if cached is not None:
                return [item.model_copy(deep=True) for item in cached]
            task = self._route_inflight.get(fingerprint)
            if task is None:
                task = asyncio.create_task(
                    self._load_routes(
                        fingerprint,
                        from_ref,
                        to_ref,
                        from_location,
                        to_location,
                        depart_at,
                        modes,
                        timezone_name,
                    )
                )
                self._route_inflight[fingerprint] = task
        try:
            routes = await asyncio.shield(task)
        finally:
            async with self._cache_lock:
                self._route_inflight.pop(fingerprint, None)
        async with self._cache_lock:
            self._route_cache[fingerprint] = routes
        return [item.model_copy(deep=True) for item in routes]

    async def _load_routes(
        self,
        fingerprint: str,
        from_ref: str,
        to_ref: str,
        from_location: LocationInput,
        to_location: LocationInput,
        depart_at: datetime,
        modes: list[str],
        timezone_name: str,
    ) -> list[TransportCandidate]:
        started = perf_counter()
        failures: dict[str, str] = {}
        live_routes: list[TransportCandidate] = []
        if not self.api_key:
            failures = {mode: "missing_api_key" for mode in modes}
        else:
            try:
                origin, destination = await asyncio.gather(
                    self._resolve_point(from_ref, from_location),
                    self._resolve_point(to_ref, to_location),
                )
            except ProviderFailure as exc:
                failures = {mode: exc.failure_type for mode in modes}
            else:
                results = await asyncio.gather(
                    *[
                        self._load_mode(
                            fingerprint,
                            mode,
                            from_ref,
                            to_ref,
                            origin,
                            destination,
                            depart_at,
                            timezone_name,
                        )
                        for mode in modes
                    ],
                    return_exceptions=True,
                )
                for mode, result in zip(modes, results, strict=True):
                    if isinstance(result, Exception):
                        if isinstance(result, ProviderFailure):
                            failures[mode] = result.failure_type
                        else:
                            failures[mode] = type(result).__name__
                    else:
                        live_routes.extend(result)

        fallback_routes: list[TransportCandidate] = []
        if failures:
            fallback_routes = await self.fallback.local_routes(
                from_ref,
                to_ref,
                from_location,
                to_location,
                depart_at,
                list(failures),
                timezone_name,
            )
            fallback_routes = [
                route.model_copy(
                    update={
                        "metadata": {
                            **route.metadata,
                            "fallback_from": self.provider_name,
                            "fallback_reason": failures.get(route.mode.value, "no_live_result"),
                            "query_fingerprint": fingerprint,
                        }
                    }
                )
                for route in fallback_routes
            ]
        combined = [*live_routes, *fallback_routes]
        modes_with_results = {item.mode.value for item in combined}
        missing_modes = [mode for mode in modes if mode not in modes_with_results]
        source_modes = {item.source_mode for item in combined}
        source_mode = (
            SourceMode.MIXED
            if len(source_modes) > 1
            else next(iter(source_modes), SourceMode.UNAVAILABLE)
        )
        self._route_traces.append(
            {
                "query_fingerprint": fingerprint,
                "from_ref": from_ref,
                "to_ref": to_ref,
                "requested_modes": modes,
                "source_mode": source_mode.value,
                "failure_types": failures,
                "missing_modes": missing_modes,
                "elapsed_ms": round((perf_counter() - started) * 1000, 2),
                "candidates": [item.model_dump(mode="json") for item in combined],
            }
        )
        return combined[:4]

    async def _resolve_point(
        self,
        ref: str,
        location: LocationInput,
    ) -> _ResolvedPoint:
        async with self._cache_lock:
            cached = self._point_cache.get(ref)
            if cached is not None:
                return cached
            task = self._point_inflight.get(ref)
            if task is None:
                task = asyncio.create_task(self._load_point(location))
                self._point_inflight[ref] = task
        try:
            point = await asyncio.shield(task)
        finally:
            async with self._cache_lock:
                self._point_inflight.pop(ref, None)
        async with self._cache_lock:
            self._point_cache[ref] = point
        return point

    async def _load_point(self, location: LocationInput) -> _ResolvedPoint:
        try:
            payload = await self._request_json(
                "geocode",
                "/v3/geocode/geo",
                {"address": location.address, "city": location.city},
            )
            geocodes = payload.get("geocodes") or []
            first = geocodes[0]
            longitude_text, latitude_text = str(first["location"]).split(",", 1)
            point = _ResolvedPoint(
                longitude=float(longitude_text),
                latitude=float(latitude_text),
                citycode=self._optional_text(first.get("citycode")),
            )
        except (KeyError, IndexError, TypeError, ValueError) as exc:
            if location.longitude is None or location.latitude is None:
                raise ProviderFailure("invalid_geocode_response") from exc
            point = _ResolvedPoint(
                longitude=location.longitude,
                latitude=location.latitude,
                citycode=None,
            )
        except ProviderFailure:
            if location.longitude is None or location.latitude is None:
                raise
            point = _ResolvedPoint(
                longitude=location.longitude,
                latitude=location.latitude,
                citycode=None,
            )
        return point

    async def _load_mode(
        self,
        fingerprint: str,
        mode: str,
        from_ref: str,
        to_ref: str,
        origin: _ResolvedPoint,
        destination: _ResolvedPoint,
        depart_at: datetime,
        timezone_name: str,
    ) -> list[TransportCandidate]:
        params: dict[str, Any] = {
            "origin": origin.coordinates,
            "destination": destination.coordinates,
            "show_fields": "cost",
        }
        if mode == "transit":
            if not origin.citycode or not destination.citycode:
                raise ProviderFailure("missing_citycode")
            path = "/v5/direction/transit/integrated"
            local_depart_at = depart_at.astimezone(ZoneInfo(timezone_name))
            params.update(
                {
                    "city1": origin.citycode,
                    "city2": destination.citycode,
                    "date": local_depart_at.strftime("%Y-%m-%d"),
                    "time": local_depart_at.strftime("%H-%M"),
                    "AlternativeRoute": 2,
                }
            )
        elif mode == "taxi":
            path = "/v5/direction/driving"
            params["strategy"] = 32
        else:
            path = f"/v5/direction/{mode}"
            params["alternative_route"] = 2
        payload = await self._request_json(f"route_{mode}", path, params)
        return self._parse_routes(
            fingerprint,
            mode,
            from_ref,
            to_ref,
            depart_at,
            payload,
        )

    def _parse_routes(
        self,
        fingerprint: str,
        mode: str,
        from_ref: str,
        to_ref: str,
        depart_at: datetime,
        payload: dict[str, Any],
    ) -> list[TransportCandidate]:
        route = payload.get("route") or {}
        raw_items = route.get("transits") if mode == "transit" else route.get("paths")
        if not isinstance(raw_items, list) or not raw_items:
            raise ProviderFailure("empty_route_result")
        candidates: list[TransportCandidate] = []
        for index, raw in enumerate(raw_items[:2]):
            cost = raw.get("cost") if isinstance(raw.get("cost"), dict) else {}
            duration_seconds = self._positive_number(cost.get("duration") or raw.get("duration"))
            if duration_seconds is None:
                raise ProviderFailure("missing_route_duration")
            distance_meters = self._nonnegative_number(raw.get("distance"))
            if mode == "taxi":
                price = self._nonnegative_number(route.get("taxi_cost")) or 0
                transfers = 0
                reliability = 82
            elif mode == "transit":
                price = self._nonnegative_number(cost.get("transit_fee")) or 0
                segments = raw.get("segments") if isinstance(raw.get("segments"), list) else []
                transfers = max(0, len(segments) - 1)
                reliability = 86
            else:
                price = 0
                transfers = 0
                reliability = 95 if mode == "walking" else 88
            duration_minutes = max(1, math.ceil(duration_seconds / 60))
            identity = f"{fingerprint}:{mode}:{index}"
            candidates.append(
                TransportCandidate(
                    candidate_id=f"amap-local-{hashlib.sha1(identity.encode()).hexdigest()[:12]}",
                    provider=self.provider_name,
                    source_mode=SourceMode.LIVE,
                    mode=TransportMode(mode),
                    direction="local",
                    from_ref=from_ref,
                    to_ref=to_ref,
                    depart_at=depart_at,
                    arrive_at=depart_at + timedelta(minutes=duration_minutes),
                    price_yuan=int(round(price)),
                    transfers=transfers,
                    reliability_score=reliability,
                    metadata={
                        "api_version": "v5",
                        "query_fingerprint": fingerprint,
                        "duration_seconds": int(duration_seconds),
                        "distance_meters": int(distance_meters or 0),
                        "cost_note": (
                            "高德预估出租车费用"
                            if mode == "taxi"
                            else "高德公交费用"
                            if mode == "transit"
                            else "未计共享单车或其他服务费"
                        ),
                    },
                )
            )
        return candidates

    async def _request_json(
        self,
        capability: str,
        path: str,
        params: dict[str, Any],
    ) -> dict[str, Any]:
        for attempt in range(1, self.max_retries + 2):
            started = perf_counter()
            status_code: int | None = None
            failure_type: str | None = None
            try:
                await self._claim_live_call()
                async with self._semaphore:
                    response = await self._client.get(
                        path,
                        params={**params, "key": self.api_key, "output": "json"},
                        timeout=self.timeout_seconds,
                    )
                status_code = response.status_code
                if response.status_code == 429 or response.status_code >= 500:
                    raise ProviderFailure(
                        f"http_{response.status_code}", status_code=response.status_code
                    )
                response.raise_for_status()
                payload = response.json()
                if str(payload.get("status")) != "1":
                    infocode = str(payload.get("infocode") or "unknown")
                    raise ProviderFailure(
                        f"api_error_{infocode}", status_code=response.status_code
                    )
                return payload
            except httpx.TimeoutException as exc:
                failure_type = "timeout"
                failure = ProviderFailure(failure_type)
                caught: Exception = exc
            except httpx.TransportError as exc:
                failure_type = "transport_error"
                failure = ProviderFailure(failure_type)
                caught = exc
            except httpx.HTTPStatusError as exc:
                failure_type = f"http_{exc.response.status_code}"
                failure = ProviderFailure(
                    failure_type, status_code=exc.response.status_code
                )
                caught = exc
            except ProviderFailure as exc:
                failure_type = exc.failure_type
                failure = exc
                caught = exc
            finally:
                elapsed_ms = round((perf_counter() - started) * 1000, 2)
                event = {
                    "capability": capability,
                    "attempt": attempt,
                    "elapsed_ms": elapsed_ms,
                    "status_code": status_code,
                    "failure_type": failure_type,
                }
                self._http_events.append(event)
                logger.info(
                    "provider=%s capability=%s attempt=%s elapsed_ms=%s status_code=%s failure_type=%s",
                    self.provider_name,
                    capability,
                    attempt,
                    elapsed_ms,
                    status_code,
                    failure_type,
                )
            retryable = failure_type in {"timeout", "transport_error", "http_429"} or (
                failure_type is not None and failure_type.startswith("http_5")
            )
            if not retryable or attempt > self.max_retries:
                raise failure from caught
            await asyncio.sleep(0)
        raise ProviderFailure("unreachable")

    async def _claim_live_call(self) -> None:
        async with self._budget_lock:
            if self._live_calls >= self.max_live_calls:
                raise ProviderFailure("call_budget_exhausted")
            self._live_calls += 1

    def provider_snapshots(self) -> list[ProviderSnapshotData]:
        if not self._route_traces:
            return []
        modes = {trace["source_mode"] for trace in self._route_traces}
        source_mode = (
            SourceMode.MIXED
            if len(modes) > 1 or SourceMode.MIXED.value in modes
            else SourceMode(next(iter(modes)))
        )
        fetched_at = datetime.now(timezone.utc)
        payload = {
            "provider": self.provider_name,
            "api_version": "v5",
            "live_call_count": self._live_calls,
            "max_live_calls": self.max_live_calls,
            "queries": self._route_traces,
            "http_events": self._http_events,
            "raw_provider_payload_persisted": False,
        }
        return [
            ProviderSnapshotData(
                provider=self.provider_name,
                capability="local_routes",
                source_mode=source_mode,
                query_fingerprint=self._fingerprint(
                    [trace["query_fingerprint"] for trace in self._route_traces]
                ),
                payload=payload,
                fetched_at=fetched_at,
                expires_at=fetched_at + timedelta(minutes=10),
            )
        ]

    async def aclose(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    @staticmethod
    def _fingerprint(value: Any) -> str:
        encoded = json.dumps(value, ensure_ascii=False, sort_keys=True).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()

    @staticmethod
    def _optional_text(value: Any) -> str | None:
        if isinstance(value, str) and value:
            return value
        return None

    @staticmethod
    def _positive_number(value: Any) -> float | None:
        try:
            number = float(value)
        except (TypeError, ValueError):
            return None
        return number if number > 0 else None

    @staticmethod
    def _nonnegative_number(value: Any) -> float | None:
        try:
            number = float(value)
        except (TypeError, ValueError):
            return None
        return number if number >= 0 else None


__all__ = ["AmapLocalRouteProvider", "ProviderFailure"]
