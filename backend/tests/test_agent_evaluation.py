import json
from pathlib import Path


def test_agent_eval_dataset_is_versioned_and_has_required_categories() -> None:
    path = Path(__file__).resolve().parents[1] / "evals" / "mission_interpret_v1.json"
    dataset = json.loads(path.read_text(encoding="utf-8"))
    assert dataset["dataset_version"] == "mission-interpret-v1"
    ids = {case["case_id"] for case in dataset["cases"]}
    assert {"complete_two_day_rail", "missing_everything", "prompt_injection", "missing_policy", "missing_origin"} <= ids
