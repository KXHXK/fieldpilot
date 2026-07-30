import httpx
import pytest

from app.main import app


MISSION_TEXT = """2026-08-06从上海虹桥站（上海市闵行区申贵路1500号）出发到杭州，行程很紧，只报高铁二等座。
任务：2026-08-06 13:30-15:30|西湖区客户现场|杭州市西湖区文三路|90分钟；
任务：2026-08-07 09:30-11:30|萧山区交付|杭州市萧山区市心北路|90分钟；
酒店每晚不超过450，餐补每天120，市内交通每天200，总预算1600。"""


def mission_command(draft: dict) -> dict:
    return {
        "origin": draft["origin"],
        "start_date": draft["start_date"],
        "end_date": draft["end_date"],
        "timezone": draft["timezone"],
        "urgency": draft["urgency"],
        "visits": [
            {
                "name": visit["name"],
                "location": {
                    "name": visit["name"],
                    "address": visit["address"],
                    "city": visit["city"],
                },
                "window_start": visit["window_start"],
                "window_end": visit["window_end"],
                "duration_minutes": visit["duration_minutes"],
                "priority": visit["priority"],
                "locked": False,
                "notes": visit["notes"],
            }
            for visit in draft["visits"]
        ],
        "expense_policy": draft["expense_policy"],
        "transport_preferences": {
            "preferred_intercity_modes": draft["preferred_intercity_modes"],
            "preferred_local_modes": draft["preferred_local_modes"],
            "minimum_transfer_minutes": 30,
            "allow_early_arrival_day": False,
        },
        "notes": draft["notes"],
    }


@pytest.mark.asyncio
async def test_natural_language_to_event_driven_revision_e2e() -> None:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        interpreted = await client.post(
            "/api/v1/agent/interpret-mission",
            json={
                "request_id": "e2e-agent-request-001",
                "text": MISSION_TEXT,
                "reference_date": "2026-07-30",
                "timezone": "Asia/Shanghai",
            },
        )
        assert interpreted.status_code == 200, interpreted.text
        assert interpreted.json()["ready_for_submission"] is True

        created = await client.post(
            "/api/v1/missions",
            json=mission_command(interpreted.json()["draft"]),
        )
        assert created.status_code == 201, created.text
        mission = created.json()
        mission_id = mission["mission_id"]

        first = await client.post(
            f"/api/v1/missions/{mission_id}/plans",
            json={"request_id": "e2e-plan-request-001", "based_on_revision": None},
        )
        assert first.status_code == 201, first.text
        activated = await client.post(
            f"/api/v1/missions/{mission_id}/revisions/1/activate",
            json={"expected_active_revision": None},
        )
        assert activated.status_code == 200, activated.text

        event_id = "e2e-event-reschedule-001"
        event = await client.post(
            f"/api/v1/missions/{mission_id}/events",
            json={
                "event_id": event_id,
                "event_type": "task_rescheduled",
                "based_on_revision": 1,
                "payload": {
                    "task_id": mission["visits"][0]["task_id"],
                    "new_window_start": "2026-08-06T14:00:00+08:00",
                    "new_window_end": "2026-08-06T16:00:00+08:00",
                },
            },
        )
        assert event.status_code == 200, event.text
        assert event.json()["application_status"] == "applied"

        second = await client.post(
            f"/api/v1/missions/{mission_id}/plans",
            json={
                "request_id": "e2e-plan-request-002",
                "based_on_revision": 1,
                "input_event_id": event_id,
            },
        )
        assert second.status_code == 201, second.text
        comparison = await client.get(
            f"/api/v1/missions/{mission_id}/revisions/1/diff/2"
        )

    assert comparison.status_code == 200, comparison.text
    assert comparison.json()["input_event_id"] == event_id
    assert comparison.json()["changes"]
