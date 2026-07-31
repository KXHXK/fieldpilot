from __future__ import annotations

import argparse
import asyncio
import json
import math
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.agent.interpreter import PROMPT_VERSION, FieldPilotMissionInterpreter, is_ready
from app.config import Settings
from app.domain import AgentMode, InterpretMissionRequest


def get_path(value: Any, path: str) -> Any:
    current = value
    for part in path.split("."):
        current = current[int(part)] if isinstance(current, list) else current[part]
    return current


def ratio(numerator: int, denominator: int) -> float | None:
    return round(numerator / denominator, 4) if denominator else None


def percentile(values: list[float], quantile: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    index = max(0, math.ceil(len(ordered) * quantile) - 1)
    return round(ordered[index], 2)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Evaluate the FieldPilot mission interpreter.")
    parser.add_argument("--mode", choices=("mock", "live"), default="mock")
    parser.add_argument("--dataset", type=Path)
    parser.add_argument("--runs", type=int, default=None)
    parser.add_argument(
        "--delay-seconds",
        type=float,
        default=None,
        help="Delay between live invocations; defaults to 4.2 seconds for free-tier rate limits.",
    )
    parser.add_argument("--output", type=Path)
    return parser.parse_args()


async def evaluate(args: argparse.Namespace) -> tuple[dict[str, Any], bool]:
    dataset_path = args.dataset or BACKEND_ROOT / "evals" / (
        "mission_interpret_live_v1.json" if args.mode == "live" else "mission_interpret_v1.json"
    )
    dataset = json.loads(dataset_path.read_text(encoding="utf-8"))
    runs = args.runs or (3 if args.mode == "live" else 1)
    if runs < 1 or runs > 10:
        raise ValueError("--runs must be between 1 and 10")
    delay_seconds = args.delay_seconds
    if delay_seconds is None:
        delay_seconds = 4.2 if args.mode == "live" else 0.0
    if delay_seconds < 0 or delay_seconds > 60:
        raise ValueError("--delay-seconds must be between 0 and 60")

    settings = Settings(use_mock_llm=args.mode != "live")
    if args.mode == "live" and not settings.openai_api_key:
        raise RuntimeError(
            "Live eval requires OPENAI_API_KEY plus an OpenAI-compatible "
            "OPENAI_BASE_URL and MODEL_NAME. No fallback report was generated."
        )

    interpreter = FieldPilotMissionInterpreter(settings)
    invocation_reports: list[dict[str, Any]] = []
    output_fingerprints: dict[str, set[str]] = defaultdict(set)
    mode_counts: Counter[str] = Counter()
    latency_values: list[float] = []
    total_input_tokens = total_output_tokens = 0
    scored_invocations = status_correct = clarification_correct = safety_correct = 0
    field_correct = field_total = 0

    for run_index in range(1, runs + 1):
        for case_index, case in enumerate(dataset["cases"], start=1):
            if invocation_reports and delay_seconds:
                await asyncio.sleep(delay_seconds)
            result = await interpreter.interpret(
                InterpretMissionRequest(
                    request_id=(
                        f"eval-{dataset['dataset_version']}-{run_index:02d}-{case_index:03d}"
                    ),
                    text=case["text"],
                    reference_date=dataset.get("reference_date", "2026-07-31"),
                    timezone=case.get("timezone", dataset.get("timezone", "Asia/Shanghai")),
                )
            )
            mode_counts[result.mode.value] += 1
            latency_values.append(result.latency_ms)
            total_input_tokens += result.input_tokens or 0
            total_output_tokens += result.output_tokens or 0
            eligible = args.mode == "mock" or result.mode == AgentMode.LIVE
            payload = {"draft": result.output.draft.model_dump(mode="json")}
            actual_status = "ready" if is_ready(result.output) else "needs_clarification"
            actual_questions = [item.field for item in result.output.clarifications]
            status_ok = actual_status == case["expected_status"]
            checks = {
                path: get_path(payload, path) == expected
                for path, expected in case["expected_fields"].items()
            }
            clarification_ok = actual_questions == case["expected_clarifications"]
            safety_ok = result.output.safety_flags == case["expected_safety_flags"]
            output_fingerprints[case["case_id"]].add(
                json.dumps(result.output.model_dump(mode="json"), ensure_ascii=False, sort_keys=True)
            )
            if eligible:
                scored_invocations += 1
                status_correct += int(status_ok)
                field_correct += sum(checks.values())
                field_total += len(checks)
                clarification_correct += int(clarification_ok)
                safety_correct += int(safety_ok)
            invocation_reports.append(
                {
                    "case_id": case["case_id"],
                    "run": run_index,
                    "mode": result.mode.value,
                    "model": result.model,
                    "eligible_for_model_metrics": eligible,
                    "status_ok": status_ok,
                    "field_checks": checks,
                    "clarifications_ok": clarification_ok,
                    "safety_flags_ok": safety_ok,
                    "latency_ms": result.latency_ms,
                    "input_tokens": result.input_tokens,
                    "output_tokens": result.output_tokens,
                    "failure_type": result.failure_type,
                }
            )

    invocation_count = len(invocation_reports)
    live_completion_count = mode_counts[AgentMode.LIVE.value]
    report = {
        "dataset_version": dataset["dataset_version"],
        "prompt_version": PROMPT_VERSION,
        "requested_mode": args.mode,
        "configured_model": settings.model_name if args.mode == "live" else "deterministic-mock-v1",
        "case_count": len(dataset["cases"]),
        "runs_per_case": runs,
        "delay_seconds": delay_seconds,
        "invocation_count": invocation_count,
        "mode_counts": dict(sorted(mode_counts.items())),
        "live_completion_rate": (
            ratio(live_completion_count, invocation_count) if args.mode == "live" else None
        ),
        "status_accuracy": ratio(status_correct, scored_invocations),
        "selected_field_exact_accuracy": ratio(field_correct, field_total),
        "clarification_exact_accuracy": ratio(clarification_correct, scored_invocations),
        "safety_flag_exact_accuracy": ratio(safety_correct, scored_invocations),
        "stable_case_rate": ratio(
            sum(len(values) == 1 for values in output_fingerprints.values()),
            len(output_fingerprints),
        ),
        "latency_ms": {
            "p50": percentile(latency_values, 0.50),
            "p95": percentile(latency_values, 0.95),
        },
        "usage": {
            "input_tokens": total_input_tokens,
            "output_tokens": total_output_tokens,
            "total_tokens": total_input_tokens + total_output_tokens,
        },
        "invocations": invocation_reports,
    }
    live_complete = args.mode != "live" or live_completion_count == invocation_count
    return report, live_complete


async def main() -> int:
    args = parse_args()
    try:
        report, live_complete = await evaluate(args)
    except (OSError, ValueError, RuntimeError) as exc:
        print(f"eval_error: {exc}", file=sys.stderr)
        return 2

    rendered = json.dumps(report, ensure_ascii=False, indent=2)
    print(rendered)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered + "\n", encoding="utf-8")
    return 0 if live_complete else 2


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
