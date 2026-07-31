from __future__ import annotations

from datetime import datetime, timezone

import httpx
import pytest

from app.domain import LocationInput, MealType, SourceMode, TransportMode
from app.providers import AmapLocalRouteProvider


def location(name: str, address: str) -> LocationInput:
    return LocationInput(name=name, address=address, city="杭州")


def geocode_payload(coordinates: str) -> dict:
    return {
        "status": "1",
        "info": "OK",
        "infocode": "10000",
        "geocodes": [{"location": coordinates, "citycode": "0571"}],
    }


@pytest.mark.asyncio
async def test_amap_v5_meal_contract_filters_budget_and_deduplicates_queries() -> None:
    observed_paths: list[str] = []
    around_query: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        observed_paths.append(request.url.path)
        if request.url.path == "/v3/geocode/geo":
            return httpx.Response(200, json=geocode_payload("120.130000,30.280000"))
        if request.url.path == "/v5/place/around":
            around_query.update(request.url.params)
            return httpx.Response(
                200,
                json={
                    "status": "1",
                    "info": "OK",
                    "infocode": "10000",
                    "pois": [
                        {
                            "id": "poi-affordable",
                            "name": "文三路工作餐",
                            "address": "文三路 88 号",
                            "distance": "320",
                            "business": {
                                "cost": "42",
                                "rating": "4.6",
                                "tag": "简餐",
                                "opentime_today": "10:30-21:00",
                            },
                        },
                        {
                            "id": "poi-over-budget",
                            "name": "高价餐厅",
                            "address": "文三路 99 号",
                            "distance": "180",
                            "business": {"cost": "168", "rating": "4.8"},
                        },
                        {
                            "id": "poi-no-price",
                            "name": "价格未知餐厅",
                            "address": "文三路 66 号",
                            "distance": "200",
                            "business": {"rating": "4.2"},
                        },
                    ],
                },
            )
        raise AssertionError(f"unexpected path: {request.url.path}")

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handler), base_url="https://restapi.amap.com"
    ) as client:
        provider = AmapLocalRouteProvider(api_key="test-key", client=client)
        args = (
            "visit-a",
            location("客户 A", "杭州市西湖区文三路"),
            MealType.LUNCH,
            60,
        )
        first = await provider.nearby_meals(*args)
        second = await provider.nearby_meals(*args)

    assert observed_paths == ["/v3/geocode/geo", "/v5/place/around"]
    assert around_query["types"] == "050000"
    assert around_query["show_fields"] == "business"
    assert around_query["sortrule"] == "distance"
    assert len(first) == 1
    assert first[0].name == "文三路工作餐"
    assert first[0].estimated_cost_yuan == 42
    assert first[0].rating == 4.6
    assert first[0].distance_meters == 320
    assert first[0].source_mode == SourceMode.LIVE
    assert [item.candidate_id for item in second] == [
        item.candidate_id for item in first
    ]
    snapshot = provider.provider_snapshots()[0]
    assert snapshot.capability == "meal_candidates"
    assert snapshot.source_mode == SourceMode.LIVE
    assert snapshot.payload["raw_provider_payload_persisted"] is False


@pytest.mark.asyncio
async def test_amap_meal_without_price_qualified_result_falls_back_honestly() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/v3/geocode/geo":
            return httpx.Response(200, json=geocode_payload("120.130000,30.280000"))
        if request.url.path == "/v5/place/around":
            return httpx.Response(
                200,
                json={
                    "status": "1",
                    "info": "OK",
                    "infocode": "10000",
                    "pois": [
                        {
                            "id": "poi-unknown-price",
                            "name": "价格未知餐厅",
                            "address": "文三路 66 号",
                            "business": {"rating": "4.2"},
                        }
                    ],
                },
            )
        raise AssertionError(f"unexpected path: {request.url.path}")

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handler), base_url="https://restapi.amap.com"
    ) as client:
        provider = AmapLocalRouteProvider(api_key="test-key", client=client)
        candidates = await provider.nearby_meals(
            "visit-a",
            location("客户 A", "杭州市西湖区文三路"),
            MealType.LUNCH,
            60,
        )

    assert candidates
    assert all(item.source_mode == SourceMode.FIXTURE for item in candidates)
    assert all(
        item.metadata["fallback_reason"] == "empty_price_qualified_meal_result"
        for item in candidates
    )
    snapshot = provider.provider_snapshots()[0]
    assert snapshot.source_mode == SourceMode.FIXTURE
    assert snapshot.payload["queries"][0]["failure_type"] == (
        "empty_price_qualified_meal_result"
    )


@pytest.mark.asyncio
async def test_amap_v5_contract_parses_live_routes_and_deduplicates_queries() -> None:
    observed_paths: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        observed_paths.append(request.url.path)
        assert "key" in request.url.params
        if request.url.path == "/v3/geocode/geo":
            coordinates = (
                "120.130000,30.280000"
                if "文三路" in request.url.params["address"]
                else "120.210000,30.210000"
            )
            return httpx.Response(200, json=geocode_payload(coordinates))
        if request.url.path == "/v5/direction/driving":
            return httpx.Response(
                200,
                json={
                    "status": "1",
                    "info": "OK",
                    "infocode": "10000",
                    "route": {
                        "taxi_cost": "28.4",
                        "paths": [
                            {"distance": "5200", "cost": {"duration": "900"}}
                        ],
                    },
                },
            )
        if request.url.path == "/v5/direction/walking":
            return httpx.Response(
                200,
                json={
                    "status": "1",
                    "info": "OK",
                    "infocode": "10000",
                    "route": {
                        "paths": [
                            {"distance": "4100", "cost": {"duration": "3600"}}
                        ]
                    },
                },
            )
        raise AssertionError(f"unexpected path: {request.url.path}")

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handler), base_url="https://restapi.amap.com"
    ) as client:
        provider = AmapLocalRouteProvider(api_key="test-key", client=client)
        args = (
            "visit-a",
            "visit-b",
            location("客户 A", "杭州市西湖区文三路"),
            location("客户 B", "杭州市滨江区江南大道"),
            datetime(2026, 8, 6, 8, tzinfo=timezone.utc),
            ["taxi", "walking"],
        )
        first = await provider.local_routes(*args)
        second = await provider.local_routes(*args)

    assert len(observed_paths) == 4
    assert {item.mode for item in first} == {TransportMode.TAXI, TransportMode.WALKING}
    assert all(item.source_mode == SourceMode.LIVE for item in first)
    taxi = next(item for item in first if item.mode == TransportMode.TAXI)
    assert taxi.price_yuan == 28
    assert taxi.metadata["duration_seconds"] == 900
    assert taxi.metadata["distance_meters"] == 5200
    assert [item.candidate_id for item in second] == [
        item.candidate_id for item in first
    ]
    snapshot = provider.provider_snapshots()[0]
    assert snapshot.source_mode == SourceMode.LIVE
    assert snapshot.payload["live_call_count"] == 4
    assert snapshot.payload["raw_provider_payload_persisted"] is False


@pytest.mark.asyncio
async def test_amap_v5_transit_contract_uses_citycodes_and_departure_time() -> None:
    transit_query: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/v3/geocode/geo":
            return httpx.Response(200, json=geocode_payload("120.130000,30.280000"))
        if request.url.path == "/v5/direction/transit/integrated":
            transit_query.update(request.url.params)
            return httpx.Response(
                200,
                json={
                    "status": "1",
                    "info": "OK",
                    "infocode": "10000",
                    "route": {
                        "transits": [
                            {
                                "distance": "7000",
                                "cost": {"duration": "1800", "transit_fee": "5"},
                                "segments": [{"bus": {}}, {"bus": {}}],
                            }
                        ]
                    },
                },
            )
        raise AssertionError(f"unexpected path: {request.url.path}")

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handler), base_url="https://restapi.amap.com"
    ) as client:
        provider = AmapLocalRouteProvider(api_key="test-key", client=client)
        routes = await provider.local_routes(
            "visit-a",
            "visit-b",
            location("客户 A", "杭州市西湖区文三路"),
            location("客户 B", "杭州市滨江区江南大道"),
            datetime(2026, 8, 6, 8, 15, tzinfo=timezone.utc),
            ["transit"],
        )

    assert transit_query["city1"] == "0571"
    assert transit_query["city2"] == "0571"
    assert transit_query["date"] == "2026-08-06"
    assert transit_query["time"] == "16-15"
    assert len(routes) == 1
    assert routes[0].mode == TransportMode.TRANSIT
    assert routes[0].price_yuan == 5
    assert routes[0].transfers == 1
    assert routes[0].arrive_at == datetime(2026, 8, 6, 8, 45, tzinfo=timezone.utc)


@pytest.mark.asyncio
async def test_timeout_retries_once_then_falls_back_with_failure_evidence() -> None:
    driving_attempts = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal driving_attempts
        if request.url.path == "/v3/geocode/geo":
            return httpx.Response(200, json=geocode_payload("120.130000,30.280000"))
        if request.url.path == "/v5/direction/driving":
            driving_attempts += 1
            raise httpx.ConnectTimeout("simulated timeout", request=request)
        raise AssertionError(f"unexpected path: {request.url.path}")

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handler), base_url="https://restapi.amap.com"
    ) as client:
        provider = AmapLocalRouteProvider(
            api_key="test-key",
            client=client,
            max_retries=1,
        )
        routes = await provider.local_routes(
            "visit-a",
            "visit-b",
            location("客户 A", "杭州市西湖区文三路"),
            location("客户 B", "杭州市滨江区江南大道"),
            datetime(2026, 8, 6, 8, tzinfo=timezone.utc),
            ["taxi"],
        )

    assert driving_attempts == 2
    assert len(routes) == 1
    assert routes[0].source_mode == SourceMode.FIXTURE
    assert routes[0].metadata["fallback_from"] == "amap-webservice-v5"
    assert routes[0].metadata["fallback_reason"] == "timeout"
    snapshot = provider.provider_snapshots()[0]
    assert snapshot.source_mode == SourceMode.FIXTURE
    timeout_events = [
        event
        for event in snapshot.payload["http_events"]
        if event["failure_type"] == "timeout"
    ]
    assert len(timeout_events) == 2
    assert all("key" not in event for event in timeout_events)


@pytest.mark.asyncio
async def test_partial_amap_failure_returns_mixed_live_and_fixture_routes() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/v3/geocode/geo":
            return httpx.Response(200, json=geocode_payload("120.130000,30.280000"))
        if request.url.path == "/v5/direction/driving":
            return httpx.Response(
                200,
                json={
                    "status": "1",
                    "info": "OK",
                    "infocode": "10000",
                    "route": {
                        "taxi_cost": "20",
                        "paths": [
                            {"distance": "3000", "cost": {"duration": "600"}}
                        ],
                    },
                },
            )
        if request.url.path == "/v5/direction/walking":
            return httpx.Response(
                200,
                json={"status": "0", "info": "INVALID_PARAMS", "infocode": "20000"},
            )
        raise AssertionError(f"unexpected path: {request.url.path}")

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handler), base_url="https://restapi.amap.com"
    ) as client:
        provider = AmapLocalRouteProvider(api_key="test-key", client=client)
        routes = await provider.local_routes(
            "visit-a",
            "visit-b",
            location("客户 A", "杭州市西湖区文三路"),
            location("客户 B", "杭州市滨江区江南大道"),
            datetime(2026, 8, 6, 8, tzinfo=timezone.utc),
            ["taxi", "walking"],
        )

    assert {item.source_mode for item in routes} == {
        SourceMode.LIVE,
        SourceMode.FIXTURE,
    }
    fallback = next(item for item in routes if item.source_mode == SourceMode.FIXTURE)
    assert fallback.metadata["fallback_reason"] == "api_error_20000"
    assert provider.provider_snapshots()[0].source_mode == SourceMode.MIXED


@pytest.mark.asyncio
async def test_missing_key_uses_fixture_without_network_call() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise AssertionError("missing-key mode must not make network calls")

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handler), base_url="https://restapi.amap.com"
    ) as client:
        provider = AmapLocalRouteProvider(api_key="", client=client)
        routes = await provider.local_routes(
            "visit-a",
            "visit-b",
            location("客户 A", "杭州市西湖区文三路"),
            location("客户 B", "杭州市滨江区江南大道"),
            datetime(2026, 8, 6, 8, tzinfo=timezone.utc),
            ["taxi"],
        )

    assert routes[0].source_mode == SourceMode.FIXTURE
    assert routes[0].metadata["fallback_reason"] == "missing_api_key"
    snapshot = provider.provider_snapshots()[0]
    assert snapshot.payload["live_call_count"] == 0


@pytest.mark.asyncio
async def test_live_call_budget_stops_remote_expansion_and_falls_back() -> None:
    observed_paths: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        observed_paths.append(request.url.path)
        if request.url.path == "/v3/geocode/geo":
            return httpx.Response(200, json=geocode_payload("120.130000,30.280000"))
        raise AssertionError("route request must be stopped by the live-call budget")

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handler), base_url="https://restapi.amap.com"
    ) as client:
        provider = AmapLocalRouteProvider(
            api_key="test-key",
            client=client,
            max_live_calls=2,
        )
        routes = await provider.local_routes(
            "visit-a",
            "visit-b",
            location("客户 A", "杭州市西湖区文三路"),
            location("客户 B", "杭州市滨江区江南大道"),
            datetime(2026, 8, 6, 8, tzinfo=timezone.utc),
            ["taxi"],
        )

    assert observed_paths == ["/v3/geocode/geo", "/v3/geocode/geo"]
    assert routes[0].source_mode == SourceMode.FIXTURE
    assert routes[0].metadata["fallback_reason"] == "call_budget_exhausted"
    snapshot = provider.provider_snapshots()[0]
    assert snapshot.payload["live_call_count"] == 2
