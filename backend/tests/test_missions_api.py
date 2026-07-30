from copy import deepcopy

import httpx
import pytest

from app.main import app


@pytest.fixture
def mission_payload() -> dict:
    return {
        "origin": {
            "name": "上海虹桥站",
            "address": "上海市闵行区申贵路1500号",
            "city": "上海",
            "longitude": 121.327,
            "latitude": 31.2,
        },
        "start_date": "2026-08-06",
        "end_date": "2026-08-07",
        "timezone": "Asia/Shanghai",
        "urgency": "tight",
        "visits": [
            {
                "name": "西湖区客户现场",
                "location": {
                    "name": "西湖区客户现场",
                    "address": "杭州市西湖区文三路",
                    "city": "杭州",
                },
                "window_start": "2026-08-06T13:30:00+08:00",
                "window_end": "2026-08-06T15:30:00+08:00",
                "duration_minutes": 90,
                "priority": "required",
                "locked": False,
                "notes": "完成现场联调",
            },
            {
                "name": "滨江区复核任务",
                "location": {
                    "name": "滨江区工作地点",
                    "address": "杭州市滨江区江南大道",
                    "city": "杭州",
                },
                "window_start": "2026-08-06T16:30:00+08:00",
                "window_end": "2026-08-06T18:30:00+08:00",
                "duration_minutes": 60,
                "priority": "high",
                "locked": False,
                "notes": "",
            },
        ],
        "expense_policy": {
            "policy_id": "demo-cn-v1",
            "policy_version": "1",
            "allowed_rail_classes": ["second_class"],
            "allowed_flight_classes": ["economy"],
            "hotel_nightly_cap_yuan": 450,
            "meal_daily_cap_yuan": 120,
            "local_transport_daily_cap_yuan": 200,
            "trip_total_cap_yuan": 1600,
        },
        "transport_preferences": {
            "preferred_intercity_modes": ["rail", "flight"],
            "preferred_local_modes": ["transit", "taxi", "walking"],
            "minimum_transfer_minutes": 30,
            "allow_early_arrival_day": False,
        },
        "notes": "跨城外勤固定场景",
    }


@pytest.mark.asyncio
async def test_create_and_read_mission_with_policy_snapshot(
    mission_payload: dict,
) -> None:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        created = await client.post("/api/v1/missions", json=mission_payload)
        assert created.status_code == 201, created.text
        payload = created.json()
        mission_id = payload["mission_id"]

        loaded = await client.get(f"/api/v1/missions/{mission_id}")

    assert loaded.status_code == 200
    assert loaded.json() == payload
    assert payload["status"] == "draft"
    assert payload["active_revision"] is None
    assert [visit["position"] for visit in payload["visits"]] == [1, 2]
    assert payload["expense_policy"]["hotel_nightly_cap_yuan"] == 450
    assert payload["expense_policy"]["snapshot_id"].startswith("pol-")


@pytest.mark.asyncio
async def test_replan_event_is_idempotent(mission_payload: dict) -> None:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        created = await client.post("/api/v1/missions", json=mission_payload)
        created_payload = created.json()
        mission_id = created_payload["mission_id"]
        task_id = created_payload["visits"][1]["task_id"]
        event = {
            "event_id": "evt-hangzhou-delay-001",
            "event_type": "task_rescheduled",
            "based_on_revision": None,
            "payload": {
                "task_id": task_id,
                "new_window_start": "2026-08-06T18:30:00+08:00",
                "new_window_end": "2026-08-06T20:30:00+08:00",
            },
        }

        first = await client.post(
            f"/api/v1/missions/{mission_id}/events", json=event
        )
        second = await client.post(
            f"/api/v1/missions/{mission_id}/events", json=event
        )

    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json()["idempotent_replay"] is False
    assert second.json()["idempotent_replay"] is True
    assert first.json()["created_at"] == second.json()["created_at"]


@pytest.mark.asyncio
async def test_replan_event_rejects_stale_revision(mission_payload: dict) -> None:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        created = await client.post("/api/v1/missions", json=mission_payload)
        mission_id = created.json()["mission_id"]
        response = await client.post(
            f"/api/v1/missions/{mission_id}/events",
            json={
                "event_id": "evt-stale-revision-001",
                "event_type": "budget_changed",
                "based_on_revision": 1,
                "payload": {"trip_total_cap_yuan": 1800},
            },
        )

    assert response.status_code == 409
    detail = response.json()["detail"]
    assert detail["code"] == "revision_conflict"
    assert detail["expected_revision"] == 1
    assert detail["active_revision"] is None


@pytest.mark.asyncio
async def test_mission_rejects_task_outside_date_range(
    mission_payload: dict,
) -> None:
    invalid = deepcopy(mission_payload)
    invalid["visits"][0]["window_start"] = "2026-08-08T13:30:00+08:00"
    invalid["visits"][0]["window_end"] = "2026-08-08T15:30:00+08:00"

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post("/api/v1/missions", json=invalid)

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_replan_event_rejects_payload_that_does_not_match_type(
    mission_payload: dict,
) -> None:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        created = await client.post("/api/v1/missions", json=mission_payload)
        mission_id = created.json()["mission_id"]
        response = await client.post(
            f"/api/v1/missions/{mission_id}/events",
            json={
                "event_id": "evt-invalid-payload-001",
                "event_type": "task_cancelled",
                "based_on_revision": None,
                "payload": {"trip_total_cap_yuan": 1800},
            },
        )

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_get_missing_mission_returns_404() -> None:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/v1/missions/msn-not-found")
    assert response.status_code == 404
