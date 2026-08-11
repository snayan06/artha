from __future__ import annotations

import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
CONTEXT_PATH = ROOT / "evals" / "agent-analyst-context-v1.json"
CASES_PATH = ROOT / "evals" / "agent-analyst-cases-v1.jsonl"

VALID_OUTCOMES = {"answer", "clarify", "refuse", "unavailable"}
VALID_TOOLS = {
    "account_overview",
    "summarize_ledger",
    "breakdown_ledger",
    "compare_periods",
    "search_transactions",
    "shared_balances",
    "detect_recurring",
    "project_cash_scenario",
    "credit_card_payment_impact",
}


def load_object(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise AssertionError(f"{path} must contain one JSON object")
    return value


def required_string(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise AssertionError(f"{label} must be a non-empty string")
    return value


def main() -> None:
    context = load_object(CONTEXT_PATH)
    if context.get("schema_version") != "agent-analyst-context-v1":
        raise AssertionError("agent context schema_version is invalid")
    if "fictional" not in str(context.get("fixture_notice", "")).lower():
        raise AssertionError("agent context must identify itself as fictional")

    account_ids = {required_string(item.get("id"), "account id") for item in context["accounts"]}
    category_ids = {required_string(item.get("id"), "category id") for item in context["categories"]}
    member_ids = {required_string(item.get("id"), "member id") for item in context["members"]}
    transaction_ids = {
        required_string(item.get("id"), "transaction id")
        for item in context["transactions"]
    }
    if len(transaction_ids) != len(context["transactions"]):
        raise AssertionError("agent context transaction IDs must be unique")

    for transaction in context["transactions"]:
        if transaction.get("source_account_id") not in account_ids:
            raise AssertionError(f"{transaction['id']}: source account is not allow-listed")
        destination = transaction.get("destination_account_id")
        if destination is not None and destination not in account_ids:
            raise AssertionError(f"{transaction['id']}: destination account is not allow-listed")
        category = transaction.get("category_id")
        if category is not None and category not in category_ids:
            raise AssertionError(f"{transaction['id']}: category is not allow-listed")
        split_ids = {split.get("member_id") for split in transaction.get("member_splits", [])}
        if not split_ids.issubset(member_ids):
            raise AssertionError(f"{transaction['id']}: member split is not allow-listed")

    cases = [
        json.loads(line)
        for line in CASES_PATH.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    if len(cases) != 30:
        raise AssertionError("agent analyst dataset must contain exactly 30 cases")
    case_ids = [required_string(case.get("id"), "case id") for case in cases]
    if len(case_ids) != len(set(case_ids)):
        raise AssertionError("agent analyst case IDs must be unique")

    for case in cases:
        case_id = case["id"]
        required_string(case.get("message"), f"{case_id}: message")
        expected = case.get("expected")
        if not isinstance(expected, dict):
            raise AssertionError(f"{case_id}: expected must be an object")
        if expected.get("outcome") not in VALID_OUTCOMES:
            raise AssertionError(f"{case_id}: unsupported outcome")
        tool_calls = expected.get("tool_calls")
        if not isinstance(tool_calls, list):
            raise AssertionError(f"{case_id}: tool_calls must be a list")
        tool_budget = expected.get("max_tool_calls")
        if (
            not isinstance(tool_budget, int)
            or isinstance(tool_budget, bool)
            or not len(tool_calls) <= tool_budget <= 3
        ):
            raise AssertionError(f"{case_id}: tool-call budget is invalid")
        turn_budget = expected.get("max_model_turns")
        if (
            not isinstance(turn_budget, int)
            or isinstance(turn_budget, bool)
            or not 1 <= turn_budget <= 2
        ):
            raise AssertionError(f"{case_id}: model-turn budget is invalid")
        deadline = expected.get("deadline_ms")
        if (
            not isinstance(deadline, int)
            or isinstance(deadline, bool)
            or not 1 <= deadline <= 12000
        ):
            raise AssertionError(f"{case_id}: deadline exceeds the 12-second limit")
        for call in tool_calls:
            if not isinstance(call, dict) or call.get("name") not in VALID_TOOLS:
                raise AssertionError(f"{case_id}: unknown tool call")
            if not isinstance(call.get("arguments"), dict):
                raise AssertionError(f"{case_id}: tool arguments must be an object")
            group = call.get("parallel_group")
            if not isinstance(group, int) or isinstance(group, bool) or group < 1:
                raise AssertionError(f"{case_id}: parallel_group must be positive")
        evidence_ids = expected.get("evidence_transaction_ids")
        if not isinstance(evidence_ids, list) or len(evidence_ids) != len(set(evidence_ids)):
            raise AssertionError(f"{case_id}: evidence IDs must be a unique list")
        if not set(evidence_ids).issubset(transaction_ids):
            raise AssertionError(f"{case_id}: evidence references unknown transactions")
        forbidden = set(expected.get("forbidden_tools", []))
        if not {"write_transaction", "execute_sql"}.issubset(forbidden):
            raise AssertionError(f"{case_id}: write and SQL tools must be forbidden")
        if forbidden.intersection(call.get("name") for call in tool_calls):
            raise AssertionError(f"{case_id}: expected call uses a forbidden tool")

    print(f"agent analyst evals: {len(cases)} cases valid")


if __name__ == "__main__":
    main()
