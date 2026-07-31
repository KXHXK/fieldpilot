from __future__ import annotations

import argparse
import json
from datetime import date
from uuid import uuid4

import httpx


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


def post(client: httpx.Client, path: str, payload: dict) -> dict:
    response = client.post(path, json=payload)
    response.raise_for_status()
    return response.json()


def preferred_option(revision: dict) -> dict:
    preferred_id = revision["bundle"]["preferred_option_id"]
    return next(
        item for item in revision["bundle"]["options"]
        if item["option_id"] == preferred_id
    )


def run(base_url: str) -> dict:
    run_id = uuid4().hex
    with httpx.Client(base_url=base_url.rstrip("/"), timeout=30) as client:
        health = client.get("/health")
        health.raise_for_status()

        interpreted = post(
            client,
            "/v1/agent/interpret-mission",
            {
                "request_id": f"smoke-agent-{run_id}",
                "text": MISSION_TEXT,
                "reference_date": date.today().isoformat(),
                "timezone": "Asia/Shanghai",
            },
        )
        if not interpreted["ready_for_submission"]:
            raise RuntimeError(
                f"Agent returned clarifications: {interpreted['clarifications']}"
            )

        mission = post(client, "/v1/missions", mission_command(interpreted["draft"]))
        mission_id = mission["mission_id"]
        first = post(
            client,
            f"/v1/missions/{mission_id}/plans",
            {
                "request_id": f"smoke-plan-r1-{run_id}",
                "based_on_revision": None,
            },
        )
        post(
            client,
            f"/v1/missions/{mission_id}/revisions/1/activate",
            {"expected_active_revision": None},
        )
        first_option = preferred_option(first)
        first_visit_segment = next(
            segment
            for segment in first_option["segments"]
            if segment["segment_type"] == "visit"
        )
        execution = post(
            client,
            f"/v1/missions/{mission_id}/execution/checkpoints",
            {
                "command_id": f"smoke-execution-lock-{run_id}",
                "based_on_revision": 1,
                "expected_version": 0,
                "action": "lock_through",
                "through_segment_id": first_visit_segment["segment_id"],
            },
        )

        event_id = f"smoke-event-{run_id}"
        event = post(
            client,
            f"/v1/missions/{mission_id}/events",
            {
                "event_id": event_id,
                "event_type": "task_rescheduled",
                "based_on_revision": 1,
                "payload": {
                    "task_id": mission["visits"][1]["task_id"],
                    "new_window_start": "2026-08-07T10:00:00+08:00",
                    "new_window_end": "2026-08-07T12:00:00+08:00",
                },
            },
        )
        second = post(
            client,
            f"/v1/missions/{mission_id}/plans",
            {
                "request_id": f"smoke-plan-r2-{run_id}",
                "based_on_revision": 1,
                "input_event_id": event_id,
            },
        )
        post(
            client,
            f"/v1/missions/{mission_id}/revisions/2/activate",
            {"expected_active_revision": 1},
        )
        completion = post(
            client,
            f"/v1/missions/{mission_id}/execution/checkpoints",
            {
                "command_id": f"smoke-execution-complete-{run_id}",
                "based_on_revision": 2,
                "expected_version": 1,
                "action": "complete_through",
                "through_segment_id": first_visit_segment["segment_id"],
            },
        )
        comparison_response = client.get(
            f"/v1/missions/{mission_id}/revisions/1/diff/2"
        )
        comparison_response.raise_for_status()
        comparison = comparison_response.json()

    second_option = preferred_option(second)
    protected_ids = set(execution["protected_segment_ids"])
    first_protected = {
        segment["segment_id"]: segment
        for segment in first_option["segments"]
        if segment["segment_id"] in protected_ids
    }
    second_by_id = {
        segment["segment_id"]: segment for segment in second_option["segments"]
    }
    return {
        "status": "passed",
        "service_version": health.json()["version"],
        "agent_mode": interpreted["trace"]["mode"],
        "mission_id": mission_id,
        "revisions": [first["revision"], second["revision"]],
        "event_application": event["application_status"],
        "execution_version": completion["version"],
        "protected_segment_count": len(protected_ids),
        "protected_prefix_unchanged": all(
            second_by_id.get(segment_id) == segment
            for segment_id, segment in first_protected.items()
        ),
        "r1_cost_yuan": first_option["costs"]["planned_total_yuan"],
        "r2_cost_yuan": second_option["costs"]["planned_total_yuan"],
        "r1_meal_cost_yuan": first_option["costs"]["meals_yuan"],
        "r2_meal_segments": sum(
            segment["segment_type"] == "meal_allowance"
            for segment in second_option["segments"]
        ),
        "provider_snapshot_count": len(second["bundle"]["provider_snapshot_ids"]),
        "changed_segments": len(comparison["changes"]),
        "preserved_segments": comparison["preserved_segment_count"],
        "source_modes": sorted(
            {segment["source_mode"] for segment in second_option["segments"]}
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run the FieldPilot v1 HTTP smoke workflow against a live API."
    )
    parser.add_argument(
        "--base-url", default="http://127.0.0.1:8000/api", help="API base URL"
    )
    args = parser.parse_args()
    print(json.dumps(run(args.base_url), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
