from __future__ import annotations

import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
CONTEXT_PATH = ROOT / "evals" / "capture-context-v1.json"
CASES_PATH = ROOT / "evals" / "capture-parser-v1.jsonl"
VALID_OUTCOMES = {"draft", "clarify", "reject"}


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise AssertionError(f"{path} must contain one JSON object")
    return value


def main() -> None:
    context = load_json(CONTEXT_PATH)
    account_ids = {item["id"] for item in context["accounts"]}
    member_ids = {item["id"] for item in context["members"]}
    category_ids = {item["id"] for item in context["categories"]}
    cases = [
        json.loads(line)
        for line in CASES_PATH.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    if len(cases) < 50:
        raise AssertionError("capture evaluation dataset must contain at least 50 cases")
    case_ids = [case["id"] for case in cases]
    if len(case_ids) != len(set(case_ids)):
        raise AssertionError("capture evaluation case IDs must be unique")

    for case in cases:
        if case.get("context") != context["id"]:
            raise AssertionError(f"{case['id']}: unknown context")
        if case.get("outcome") not in VALID_OUTCOMES:
            raise AssertionError(f"{case['id']}: invalid outcome")
        if not isinstance(case.get("utterance"), str) or not case["utterance"].strip():
            raise AssertionError(f"{case['id']}: utterance is required")
        expected = case.get("expected")
        if not isinstance(expected, dict) or not expected:
            raise AssertionError(f"{case['id']}: expected object is required")
        if case["outcome"] != "draft":
            continue
        amount = expected.get("amount_paise")
        if not isinstance(amount, int) or isinstance(amount, bool) or amount <= 0:
            raise AssertionError(f"{case['id']}: draft amount_paise must be positive integer")
        source_id = expected.get("source_account_id")
        if source_id not in account_ids:
            raise AssertionError(f"{case['id']}: source account is not allow-listed")
        destination_id = expected.get("destination_account_id")
        if destination_id is not None and destination_id not in account_ids:
            raise AssertionError(f"{case['id']}: destination account is not allow-listed")
        if expected.get("kind") == "transfer" and destination_id == source_id:
            raise AssertionError(f"{case['id']}: transfer accounts must differ")
        if expected.get("category_id") is not None and expected["category_id"] not in category_ids:
            raise AssertionError(f"{case['id']}: category is not allow-listed")
        if any(member_id not in member_ids for member_id in expected.get("member_ids", [])):
            raise AssertionError(f"{case['id']}: member is not allow-listed")

    print(f"capture evals: {len(cases)} cases valid")


if __name__ == "__main__":
    main()
