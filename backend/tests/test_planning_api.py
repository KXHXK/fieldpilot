import json
from copy import deepcopy
from pathlib import Path

import httpx
import pytest

from app.db import SessionFactory
from app.db.models import ProviderSnapshotRecord
from app.config import settings
from app.domain import MissionRead, PlanRevisionRead, SegmentType
from app.main import app
from app.planning import PlanVerificationError, PlanVerifier, PolicyEngine
from app.providers.fixture import FixtureCandidateProvider


def load_mission_payload() -> dict:
    path = Path(__file__).resolve().parents[2] / "examples" / "hangzhou-mission-v1.json"
    return json.loads(path.read_text(encoding="utf-8"))


async def create_mission(client: httpx.AsyncClient, payload: dict | None = None) -> dict:
    response = await client.post(
        "/api/v1/missions", json=payload or load_mission_payload()
    )
    assert response.status_code == 201, response.text
    return response.json()


@pytest.mark.asyncio
async def test_generate_plan_persists_verified_fixture_options() -> None:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        mission = await create_mission(client)
        response = await client.post(
            f"/api/v1/missions/{mission['mission_id']}/plans",
            json={"request_id": "plan-hangzhou-fixture-001", "based_on_revision": None},
        )
        assert response.status_code == 201, response.text
        revision = response.json()
        listed = await client.get(
            f"/api/v1/missions/{mission['mission_id']}/revisions"
        )
        loaded = await client.get(
            f"/api/v1/missions/{mission['mission_id']}/revisions/1"
        )

    assert revision["revision"] == 1
    assert revision["status"] == "proposed"
    assert revision["idempotent_replay"] is False
    assert 1 <= len(revision["bundle"]["options"]) <= 3
    assert revision["bundle"]["preferred_option_id"] == revision["bundle"]["options"][0][
        "option_id"
    ]
    expected_tasks = {visit["task_id"] for visit in mission["visits"]}
    for option in revision["bundle"]["options"]:
        observed_tasks = {
            segment["task_id"]
            for segment in option["segments"]
            if segment["segment_type"] == "visit"
        }
        assert observed_tasks == expected_tasks
        assert all(
            decision["status"] == "pass"
            for decision in option["policy_decisions"]
        )
        assert option["costs"]["planned_total_yuan"] <= 1600
        assert any("Fixture" in warning for warning in option["warnings"])
    assert listed.status_code == 200
    assert len(listed.json()) == 1
    assert loaded.json() == revision

    snapshot_id = revision["bundle"]["provider_snapshot_ids"][0]
    async with SessionFactory() as session:
        snapshot = await session.get(ProviderSnapshotRecord, snapshot_id)
        assert snapshot is not None
        assert snapshot.source_mode == "fixture"
        assert snapshot.provider == "fieldpilot-fixture-v1"


@pytest.mark.asyncio
async def test_plan_request_is_idempotent() -> None:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        mission = await create_mission(client)
        request = {"request_id": "plan-idempotent-001", "based_on_revision": None}
        first = await client.post(
            f"/api/v1/missions/{mission['mission_id']}/plans", json=request
        )
        second = await client.post(
            f"/api/v1/missions/{mission['mission_id']}/plans", json=request
        )

    assert first.status_code == 201
    assert second.status_code == 201
    assert first.json()["revision_id"] == second.json()["revision_id"]
    assert second.json()["idempotent_replay"] is True


@pytest.mark.asyncio
async def test_event_linked_revision_exposes_explainable_diff() -> None:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        mission = await create_mission(client)
        mission_id = mission["mission_id"]
        first = await client.post(
            f"/api/v1/missions/{mission_id}/plans",
            json={"request_id": "plan-before-event-001", "based_on_revision": None},
        )
        assert first.status_code == 201, first.text
        activated = await client.post(
            f"/api/v1/missions/{mission_id}/revisions/1/activate",
            json={"expected_active_revision": None},
        )
        assert activated.status_code == 200, activated.text
        task_id = mission["visits"][1]["task_id"]
        event_id = "evt-reschedule-for-diff-001"
        event = await client.post(
            f"/api/v1/missions/{mission_id}/events",
            json={
                "event_id": event_id,
                "event_type": "task_rescheduled",
                "based_on_revision": 1,
                "payload": {
                    "task_id": task_id,
                    "new_window_start": "2026-08-06T17:30:00+08:00",
                    "new_window_end": "2026-08-06T19:30:00+08:00",
                },
            },
        )
        assert event.status_code == 200, event.text
        second = await client.post(
            f"/api/v1/missions/{mission_id}/plans",
            json={
                "request_id": "plan-after-event-001",
                "based_on_revision": 1,
                "input_event_id": event_id,
            },
        )
        diff = await client.get(
            f"/api/v1/missions/{mission_id}/revisions/1/diff/2"
        )

    assert second.status_code == 201, second.text
    assert second.json()["input_event_id"] == event_id
    assert diff.status_code == 200, diff.text
    payload = diff.json()
    assert payload["input_event_id"] == event_id
    assert any(
        change["identity"].startswith(f"task:{task_id}")
        and change["change_type"] == "changed"
        for change in payload["changes"]
    )
    assert payload["preserved_segment_count"] > 0


@pytest.mark.asyncio
async def test_plan_rejects_unknown_input_event() -> None:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        mission = await create_mission(client)
        response = await client.post(
            f"/api/v1/missions/{mission['mission_id']}/plans",
            json={
                "request_id": "plan-unknown-event-001",
                "based_on_revision": None,
                "input_event_id": "evt-does-not-exist",
            },
        )

    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "input_event_not_found"


@pytest.mark.asyncio
async def test_activate_revision_and_reject_stale_activation() -> None:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        mission = await create_mission(client)
        mission_id = mission["mission_id"]
        first = await client.post(
            f"/api/v1/missions/{mission_id}/plans",
            json={"request_id": "plan-activation-001", "based_on_revision": None},
        )
        assert first.status_code == 201, first.text
        activated = await client.post(
            f"/api/v1/missions/{mission_id}/revisions/1/activate",
            json={"expected_active_revision": None},
        )
        replay = await client.post(
            f"/api/v1/missions/{mission_id}/revisions/1/activate",
            json={"expected_active_revision": None},
        )
        second = await client.post(
            f"/api/v1/missions/{mission_id}/plans",
            json={"request_id": "plan-activation-002", "based_on_revision": 1},
        )
        stale = await client.post(
            f"/api/v1/missions/{mission_id}/revisions/2/activate",
            json={"expected_active_revision": None},
        )
        activate_second = await client.post(
            f"/api/v1/missions/{mission_id}/revisions/2/activate",
            json={"expected_active_revision": 1},
        )
        revisions = await client.get(f"/api/v1/missions/{mission_id}/revisions")
        current_mission = await client.get(f"/api/v1/missions/{mission_id}")

    assert activated.status_code == 200
    assert activated.json()["idempotent_replay"] is False
    assert replay.status_code == 200
    assert replay.json()["idempotent_replay"] is True
    assert second.status_code == 201, second.text
    assert second.json()["revision"] == 2
    assert stale.status_code == 409
    assert stale.json()["detail"]["code"] == "revision_conflict"
    assert activate_second.status_code == 200
    assert [item["status"] for item in revisions.json()] == ["superseded", "active"]
    assert current_mission.json()["active_revision"] == 2
    assert current_mission.json()["status"] == "active"


@pytest.mark.asyncio
async def test_no_feasible_plan_reports_policy_reason() -> None:
    payload = load_mission_payload()
    payload["expense_policy"]["trip_total_cap_yuan"] = 100
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        mission = await create_mission(client, payload)
        response = await client.post(
            f"/api/v1/missions/{mission['mission_id']}/plans",
            json={"request_id": "plan-over-budget-001", "based_on_revision": None},
        )

    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "no_feasible_plan"
    assert response.json()["detail"]["reasons"]


@pytest.mark.asyncio
async def test_independent_verifier_rejects_tampered_visit() -> None:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        mission_payload = await create_mission(client)
        response = await client.post(
            f"/api/v1/missions/{mission_payload['mission_id']}/plans",
            json={"request_id": "plan-verifier-001", "based_on_revision": None},
        )
    mission = MissionRead.model_validate(mission_payload)
    revision = PlanRevisionRead.model_validate(response.json())
    option = revision.bundle.options[0].model_copy(deep=True)
    visit_segment = next(
        segment
        for segment in option.segments
        if segment.segment_type == SegmentType.VISIT
    )
    visit_segment.end_at = visit_segment.end_at.replace(hour=23)

    with pytest.raises(PlanVerificationError) as captured:
        PlanVerifier(PolicyEngine()).verify(mission, option)
    assert any("时间窗" in violation or "重叠" in violation for violation in captured.value.violations)


@pytest.mark.asyncio
async def test_amap_mode_without_key_persists_honest_fallback_snapshot(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "local_route_provider", "amap")
    monkeypatch.setattr(settings, "amap_api_key", "")
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        mission = await create_mission(client)
        response = await client.post(
            f"/api/v1/missions/{mission['mission_id']}/plans",
            json={"request_id": "plan-amap-fallback-001", "based_on_revision": None},
        )

    assert response.status_code == 201, response.text
    revision = response.json()
    assert len(revision["bundle"]["provider_snapshot_ids"]) == 2
    assert any(
        "高德失败后降级" in warning
        for option in revision["bundle"]["options"]
        for warning in option["warnings"]
    )
    route_snapshot_id = revision["bundle"]["provider_snapshot_ids"][1]
    async with SessionFactory() as session:
        snapshot = await session.get(ProviderSnapshotRecord, route_snapshot_id)
        assert snapshot is not None
        assert snapshot.provider == "amap-webservice-v5"
        assert snapshot.capability == "local_routes"
        assert snapshot.source_mode == "fixture"
        assert snapshot.payload["live_call_count"] == 0
        assert all(
            set(trace["failure_types"].values()) == {"missing_api_key"}
            for trace in snapshot.payload["queries"]
        )


@pytest.mark.asyncio
async def test_fixture_routes_are_stable_across_equivalent_mission_ids() -> None:
    payload = load_mission_payload()
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        first_payload = await create_mission(client, deepcopy(payload))
        second_payload = await create_mission(client, deepcopy(payload))

    first = MissionRead.model_validate(first_payload)
    second = MissionRead.model_validate(second_payload)
    provider = FixtureCandidateProvider()
    first_bundle = provider.search(first)
    second_bundle = provider.search(second)
    first_routes = await provider.local_routes(
        first.visits[0].task_id,
        first.visits[1].task_id,
        first.visits[0].location,
        first.visits[1].location,
        first.visits[0].window_end,
        first.transport_preferences.preferred_local_modes,
    )
    second_routes = await provider.local_routes(
        second.visits[0].task_id,
        second.visits[1].task_id,
        second.visits[0].location,
        second.visits[1].location,
        second.visits[0].window_end,
        second.transport_preferences.preferred_local_modes,
    )

    assert first.mission_id != second.mission_id
    assert first.visits[0].task_id != second.visits[0].task_id
    assert first_bundle.query_fingerprint == second_bundle.query_fingerprint
    assert [route.candidate_id for route in first_routes] == [
        route.candidate_id for route in second_routes
    ]
    assert [route.price_yuan for route in first_routes] == [
        route.price_yuan for route in second_routes
    ]
    assert [
        int((route.arrive_at - route.depart_at).total_seconds())
        for route in first_routes
    ] == [
        int((route.arrive_at - route.depart_at).total_seconds())
        for route in second_routes
    ]
