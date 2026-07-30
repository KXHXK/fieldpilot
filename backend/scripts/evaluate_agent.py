from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path
from typing import Any

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.agent.interpreter import FieldPilotMissionInterpreter, is_ready
from app.config import Settings
from app.domain import InterpretMissionRequest


def get_path(value: dict[str, Any], path: str) -> Any:
    current: Any = value
    for part in path.split("."):
        current = current[part]
    return current


async def main() -> None:
    dataset_path = Path(__file__).resolve().parents[1] / "evals" / "mission_interpret_v1.json"
    dataset = json.loads(dataset_path.read_text(encoding="utf-8"))
    interpreter = FieldPilotMissionInterpreter(Settings(use_mock_llm=True, _env_file=None))
    case_reports = []
    field_correct = field_total = status_correct = clarification_correct = safety_correct = 0
    for index, case in enumerate(dataset["cases"], start=1):
        run = await interpreter.interpret(InterpretMissionRequest(
            request_id=f"eval-{dataset['dataset_version']}-{index:03d}",
            text=case["text"], reference_date="2026-07-30", timezone="Asia/Shanghai"))
        payload = {"draft": run.output.draft.model_dump(mode="json")}
        actual_status = "ready" if is_ready(run.output) else "needs_clarification"
        status_ok = actual_status == case["expected_status"]
        status_correct += int(status_ok)
        checks = {path: get_path(payload, path) == expected for path, expected in case["expected_fields"].items()}
        field_correct += sum(checks.values()); field_total += len(checks)
        actual_questions = [item.field for item in run.output.clarifications]
        clarification_ok = actual_questions == case["expected_clarifications"]
        clarification_correct += int(clarification_ok)
        safety_ok = run.output.safety_flags == case["expected_safety_flags"]
        safety_correct += int(safety_ok)
        case_reports.append({"case_id": case["case_id"], "status_ok": status_ok,
                             "field_checks": checks, "clarifications_ok": clarification_ok,
                             "safety_flags_ok": safety_ok})
    count = len(case_reports)
    report = {
        "dataset_version": dataset["dataset_version"], "mode": "deterministic-mock-v1",
        "case_count": count, "status_accuracy": status_correct / count,
        "field_exact_accuracy": field_correct / field_total if field_total else 1.0,
        "clarification_exact_accuracy": clarification_correct / count,
        "safety_flag_exact_accuracy": safety_correct / count,
        "cases": case_reports,
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
