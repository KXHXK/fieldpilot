import json
from copy import deepcopy
from pathlib import Path

import httpx
import pytest

from app.domain import MissionRead, PlanOption, PlanRevisionRead
from app.main import app
from app.planning import PlanVerificationError, PlanVerifier, PolicyEngine


def load_mission_payload() -> dict:
    path = Path(__file__).resolve().parents[2] / "examples" / "hangzhou-mission-v1.json"
    return json.loads(path.read_text(encoding="utf-8"))


async def create_active_plan(client: httpx.AsyncClient) -> tuple[dict, dict]:
    created = await client.post("/api/v1/missions", json=load_mission_payload())
    assert created.status_code == 201, created.text
    mission = created.json()
    generated = await client.post(
        f"/api/v1/missions/{mission['mission_id']}/plans",
        json={"request_id": "plan-execution-base-001", "based_on_revision": None},
    )
    assert generated.status_code == 201, generated.text
    activated = await client.post(
        f"/api/v1/missions/{mission['mission_id']}/revisions/1/activate",
        json={"expected_active_revision": None},
    )
    assert activated.status_code == 200, activated.text
    return mission, generated.json()


def first_visit_segment(revision: dict) -> dict:
    preferred_id = revision["bundle"]["preferred_option_id"]
    preferred = next(
        item for item in revision["bundle"]["options"]
        if item["option_id"] == preferred_id
    )
    return next(
        item for item in preferred["segments"]
        if item["segment_type"] == "visit"
    )


@pytest.mark.asyncio
async def test_execution_checkpoint_is_monotonic_idempotent_and_updates_tasks() -> None:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        mission, revision = await create_active_plan(client)
        mission_id = mission["mission_id"]
        visit_segment = first_visit_segment(revision)

        empty = await client.get(f"/api/v1/missions/{mission_id}/execution")
        lock_command = {
            "command_id": "exec-lock-first-visit-001",
            "based_on_revision": 1,
            "expected_version": 0,
            "action": "lock_through",
            "through_segment_id": visit_segment["segment_id"],
        }
        locked = await client.post(
            f"/api/v1/missions/{mission_id}/execution/checkpoints",
            json=lock_command,
        )
        replay = await client.post(
            f"/api/v1/missions/{mission_id}/execution/checkpoints",
            json=lock_command,
        )
        completed = await client.post(
            f"/api/v1/missions/{mission_id}/execution/checkpoints",
            json={
                "command_id": "exec-complete-first-visit-001",
                "based_on_revision": 1,
                "expected_version": 1,
                "action": "complete_through",
                "through_segment_id": visit_segment["segment_id"],
            },
        )
        loaded_mission = await client.get(f"/api/v1/missions/{mission_id}")

    assert empty.status_code == 200
    assert empty.json()["version"] == 0
    assert locked.status_code == 200, locked.text
    assert locked.json()["version"] == 1
    assert locked.json()["locked_through_segment_id"] == visit_segment["segment_id"]
    assert visit_segment["segment_id"] in locked.json()["protected_segment_ids"]
    assert replay.status_code == 200
    assert replay.json()["idempotent_replay"] is True
    assert replay.json()["version"] == 1
    assert completed.status_code == 200, completed.text
    assert completed.json()["version"] == 2
    assert completed.json()["completed_through_segment_id"] == visit_segment["segment_id"]
    first_task = next(
        item for item in loaded_mission.json()["visits"]
        if item["task_id"] == visit_segment["task_id"]
    )
    assert first_task["locked"] is True
    assert first_task["completed"] is True


@pytest.mark.asyncio
async def test_execution_checkpoint_rejects_unsafe_transitions_and_conflicts() -> None:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        mission, revision = await create_active_plan(client)
        mission_id = mission["mission_id"]
        visit_segment = first_visit_segment(revision)
        complete_without_lock = await client.post(
            f"/api/v1/missions/{mission_id}/execution/checkpoints",
            json={
                "command_id": "exec-complete-without-lock-001",
                "based_on_revision": 1,
                "expected_version": 0,
                "action": "complete_through",
                "through_segment_id": visit_segment["segment_id"],
            },
        )
        locked = await client.post(
            f"/api/v1/missions/{mission_id}/execution/checkpoints",
            json={
                "command_id": "exec-conflict-seed-001",
                "based_on_revision": 1,
                "expected_version": 0,
                "action": "lock_through",
                "through_segment_id": visit_segment["segment_id"],
            },
        )
        stale = await client.post(
            f"/api/v1/missions/{mission_id}/execution/checkpoints",
            json={
                "command_id": "exec-stale-version-001",
                "based_on_revision": 1,
                "expected_version": 0,
                "action": "complete_through",
                "through_segment_id": visit_segment["segment_id"],
            },
        )
        command_conflict = await client.post(
            f"/api/v1/missions/{mission_id}/execution/checkpoints",
            json={
                "command_id": "exec-conflict-seed-001",
                "based_on_revision": 1,
                "expected_version": 1,
                "action": "complete_through",
                "through_segment_id": visit_segment["segment_id"],
            },
        )

    assert complete_without_lock.status_code == 422
    assert complete_without_lock.json()["detail"]["code"] == "completion_exceeds_lock"
    assert locked.status_code == 200
    assert stale.status_code == 409
    assert stale.json()["detail"]["code"] == "execution_version_conflict"
    assert command_conflict.status_code == 409
    assert command_conflict.json()["detail"]["code"] == "execution_command_conflict"


@pytest.mark.asyncio
async def test_replan_preserves_locked_prefix_and_only_solves_suffix() -> None:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        mission, first_revision = await create_active_plan(client)
        mission_id = mission["mission_id"]
        first_visit = first_visit_segment(first_revision)
        locked = await client.post(
            f"/api/v1/missions/{mission_id}/execution/checkpoints",
            json={
                "command_id": "exec-prefix-replan-lock-001",
                "based_on_revision": 1,
                "expected_version": 0,
                "action": "lock_through",
                "through_segment_id": first_visit["segment_id"],
            },
        )
        assert locked.status_code == 200, locked.text
        event_id = "evt-prefix-replan-second-task-001"
        event = await client.post(
            f"/api/v1/missions/{mission_id}/events",
            json={
                "event_id": event_id,
                "event_type": "task_rescheduled",
                "based_on_revision": 1,
                "payload": {
                    "task_id": mission["visits"][1]["task_id"],
                    "new_window_start": "2026-08-06T17:30:00+08:00",
                    "new_window_end": "2026-08-06T19:30:00+08:00",
                },
            },
        )
        assert event.status_code == 200, event.text
        second = await client.post(
            f"/api/v1/missions/{mission_id}/plans",
            json={
                "request_id": "plan-protected-suffix-001",
                "based_on_revision": 1,
                "input_event_id": event_id,
            },
        )
        diff = await client.get(
            f"/api/v1/missions/{mission_id}/revisions/1/diff/2"
        )
        immutable_event = await client.post(
            f"/api/v1/missions/{mission_id}/events",
            json={
                "event_id": "evt-immutable-first-task-001",
                "event_type": "task_rescheduled",
                "based_on_revision": 1,
                "payload": {
                    "task_id": mission["visits"][0]["task_id"],
                    "new_window_start": "2026-08-06T14:00:00+08:00",
                    "new_window_end": "2026-08-06T16:00:00+08:00",
                },
            },
        )

    assert second.status_code == 201, second.text
    checkpoint = locked.json()
    protected_ids = set(checkpoint["protected_segment_ids"])
    first_preferred = next(
        item for item in first_revision["bundle"]["options"]
        if item["option_id"] == first_revision["bundle"]["preferred_option_id"]
    )
    original = {
        item["segment_id"]: item
        for item in first_preferred["segments"]
        if item["segment_id"] in protected_ids
    }
    cutoff = checkpoint["locked_through_at"]
    for option in second.json()["bundle"]["options"]:
        observed = {item["segment_id"]: item for item in option["segments"]}
        assert {item: observed[item] for item in protected_ids} == original
        assert all(
            item["segment_id"] in protected_ids or item["start_at"] >= cutoff
            for item in option["segments"]
        )
    assert diff.status_code == 200, diff.text
    assert diff.json()["preserved_segment_count"] >= len(protected_ids)
    assert immutable_event.status_code == 422
    assert immutable_event.json()["detail"]["code"] == "task_immutable"


@pytest.mark.asyncio
async def test_verifier_rejects_tampered_protected_prefix() -> None:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        mission_payload, revision_payload = await create_active_plan(client)
        loaded = await client.get(
            f"/api/v1/missions/{mission_payload['mission_id']}"
        )

    mission = MissionRead.model_validate(loaded.json())
    revision = PlanRevisionRead.model_validate(revision_payload)
    preferred = next(
        item
        for item in revision.bundle.options
        if item.option_id == revision.bundle.preferred_option_id
    )
    checkpoint = next(
        item for item in preferred.segments if item.segment_type.value == "visit"
    )
    protected = [
        item for item in preferred.segments if item.end_at <= checkpoint.end_at
    ]
    tampered_payload = deepcopy(preferred.model_dump(mode="json"))
    segment = next(
        item
        for item in tampered_payload["segments"]
        if item["segment_id"] == checkpoint.segment_id
    )
    segment["title"] = "被篡改的已锁定任务"
    tampered = PlanOption.model_validate(tampered_payload)

    with pytest.raises(PlanVerificationError) as exc_info:
        PlanVerifier(PolicyEngine()).verify(
            mission,
            tampered,
            protected_prefix=protected,
            resume_from_segment_id=checkpoint.segment_id,
        )

    assert "被修改" in str(exc_info.value)
