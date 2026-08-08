from __future__ import annotations

import argparse
import asyncio
import json
import math
import time
from collections import Counter
from collections.abc import Awaitable, Callable, Sequence
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from functools import partial
from pathlib import Path
from typing import Any, Literal, cast

import httpx
from google.genai import errors as genai_errors

from artha_api.assistant import (
    AssistantCompletion,
    AssistantFinancialContext,
    AssistantSettings,
    ChartWidget,
    LlmProvider,
    LocalFinancialAssistant,
    MetricWidget,
    TableWidget,
    TagCategory,
    TagSuggestion,
    TagSuggestionRequest,
)

TAG_CATEGORIES = (
    TagCategory(id="food", name="Food"),
    TagCategory(id="transport", name="Transport"),
    TagCategory(id="shopping", name="Shopping"),
    TagCategory(id="bills", name="Bills"),
    TagCategory(id="health", name="Health"),
    TagCategory(id="entertainment", name="Entertainment"),
    TagCategory(id="housing", name="Housing"),
    TagCategory(id="income", name="Income"),
    TagCategory(id="travel", name="Travel"),
)
VALID_INTENTS = {
    "summary",
    "spending",
    "income",
    "cashflow",
    "shared",
    "transactions",
    "clarification",
    "unsupported",
}
VALID_WIDGET_TYPES = {"metric", "chart", "table", "clarification"}


@dataclass(frozen=True, slots=True)
class TagEvalCase:
    id: str
    description: str
    amount_paise: int
    direction: Literal["expense", "income"]
    expected_category_id: str | None
    tags: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class TagScore:
    case_id: str
    tags: tuple[str, ...]
    expected_category_id: str | None
    actual_category_id: str | None
    passed: bool
    grounding_violation: bool
    latency_ms: int | None = None
    unavailable: bool = False
    failure_kind: str | None = None


@dataclass(frozen=True, slots=True)
class AssistantEvalCase:
    id: str
    message: str
    expected_intent: str
    required_widget_types: tuple[str, ...]
    expected_values_paise: tuple[int, ...]
    tags: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class AssistantEvalSuite:
    context: AssistantFinancialContext
    cases: tuple[AssistantEvalCase, ...]


@dataclass(frozen=True, slots=True)
class AssistantScore:
    case_id: str
    tags: tuple[str, ...]
    expected_intent: str
    actual_intent: str | None
    required_widget_types: tuple[str, ...]
    actual_widget_types: tuple[str, ...]
    expected_values_paise: tuple[int, ...]
    actual_values_paise: tuple[int, ...]
    passed: bool
    numeric_mismatch: bool
    latency_ms: int | None = None
    unavailable: bool = False
    failure_kind: str | None = None


def _object(value: object, *, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"{label} must be an object")
    return cast(dict[str, Any], value)


def _strings(value: object, *, label: str) -> tuple[str, ...]:
    if not isinstance(value, list) or any(
        not isinstance(item, str) or not item.strip() for item in value
    ):
        raise ValueError(f"{label} must be a list of non-empty strings")
    return tuple(cast(list[str], value))


def _integers(value: object, *, label: str) -> tuple[int, ...]:
    if not isinstance(value, list) or any(
        not isinstance(item, int) or isinstance(item, bool) for item in value
    ):
        raise ValueError(f"{label} must be a list of integers")
    return tuple(cast(list[int], value))


def load_tag_suite(path: Path, *, minimum_cases: int = 30) -> tuple[TagEvalCase, ...]:
    allowed_ids = {category.id for category in TAG_CATEGORIES}
    cases: list[TagEvalCase] = []
    seen: set[str] = set()
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        payload = _object(json.loads(line), label=f"tag line {line_number}")
        case_id = str(payload.get("id", "")).strip()
        if not case_id or case_id in seen:
            raise ValueError(f"invalid or duplicate tag case ID: {case_id!r}")
        seen.add(case_id)
        direction = payload.get("direction")
        if direction not in {"expense", "income"}:
            raise ValueError(f"{case_id}: invalid direction")
        amount = payload.get("amount_paise")
        if not isinstance(amount, int) or isinstance(amount, bool) or amount <= 0:
            raise ValueError(f"{case_id}: amount_paise must be positive")
        expected = payload.get("expected_category_id")
        if expected is not None and expected not in allowed_ids:
            raise ValueError(f"{case_id}: expected category is not allow-listed")
        description = str(payload.get("description", "")).strip()
        if not description:
            raise ValueError(f"{case_id}: description is required")
        tags = _strings(payload.get("tags"), label=f"{case_id}.tags")
        cases.append(
            TagEvalCase(
                id=case_id,
                description=description,
                amount_paise=amount,
                direction=cast(Literal["expense", "income"], direction),
                expected_category_id=cast(str | None, expected),
                tags=tags,
            )
        )
    if len(cases) < minimum_cases:
        raise ValueError(f"tag suite requires at least {minimum_cases} cases")
    return tuple(cases)


def load_assistant_suite(
    context_path: Path,
    dataset_path: Path,
    *,
    minimum_cases: int = 24,
) -> AssistantEvalSuite:
    context = AssistantFinancialContext.model_validate_json(
        context_path.read_text(encoding="utf-8")
    )
    cases: list[AssistantEvalCase] = []
    seen: set[str] = set()
    for line_number, line in enumerate(dataset_path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        payload = _object(json.loads(line), label=f"assistant line {line_number}")
        case_id = str(payload.get("id", "")).strip()
        if not case_id or case_id in seen:
            raise ValueError(f"invalid or duplicate assistant case ID: {case_id!r}")
        seen.add(case_id)
        message = str(payload.get("message", "")).strip()
        intent = str(payload.get("expected_intent", "")).strip()
        if not message or intent not in VALID_INTENTS:
            raise ValueError(f"{case_id}: invalid message or intent")
        widgets = _strings(payload.get("required_widget_types"), label=f"{case_id}.widgets")
        if not widgets or any(widget not in VALID_WIDGET_TYPES for widget in widgets):
            raise ValueError(f"{case_id}: invalid required widget")
        cases.append(
            AssistantEvalCase(
                id=case_id,
                message=message,
                expected_intent=intent,
                required_widget_types=widgets,
                expected_values_paise=_integers(
                    payload.get("expected_values_paise"),
                    label=f"{case_id}.expected_values_paise",
                ),
                tags=_strings(payload.get("tags"), label=f"{case_id}.tags"),
            )
        )
    if len(cases) < minimum_cases:
        raise ValueError(f"assistant suite requires at least {minimum_cases} cases")
    return AssistantEvalSuite(context=context, cases=tuple(cases))


def score_tag_case(case: TagEvalCase, suggestion: TagSuggestion) -> TagScore:
    allowed_ids = {category.id for category in TAG_CATEGORIES}
    actual = suggestion.category_id
    grounding_violation = actual is not None and actual not in allowed_ids
    return TagScore(
        case_id=case.id,
        tags=case.tags,
        expected_category_id=case.expected_category_id,
        actual_category_id=actual,
        passed=not grounding_violation and actual == case.expected_category_id,
        grounding_violation=grounding_violation,
    )


def _assistant_values(completion: AssistantCompletion) -> tuple[int, ...]:
    values: list[int] = []
    for widget in completion.widgets:
        if isinstance(widget, MetricWidget):
            values.append(widget.value_paise)
        elif isinstance(widget, ChartWidget):
            values.extend(point.value_paise for point in widget.points)
        elif isinstance(widget, TableWidget):
            values.extend(row.amount_paise for row in widget.rows)
    return tuple(values)


def score_assistant_case(
    case: AssistantEvalCase, completion: AssistantCompletion
) -> AssistantScore:
    widget_types = tuple(widget.type for widget in completion.widgets)
    values = _assistant_values(completion)
    numeric_mismatch = values != case.expected_values_paise
    widget_mismatch = widget_types != case.required_widget_types
    passed = (
        completion.intent == case.expected_intent and not widget_mismatch and not numeric_mismatch
    )
    return AssistantScore(
        case_id=case.id,
        tags=case.tags,
        expected_intent=case.expected_intent,
        actual_intent=str(completion.intent),
        required_widget_types=case.required_widget_types,
        actual_widget_types=widget_types,
        expected_values_paise=case.expected_values_paise,
        actual_values_paise=values,
        passed=passed,
        numeric_mismatch=numeric_mismatch,
    )


def build_decision(summaries: dict[str, dict[str, float | int]]) -> dict[str, object]:
    capture = summaries["capture"]
    tag = summaries["tag"]
    assistant = summaries["assistant"]
    gates = {
        "capture_coverage": float(capture["coverage"]) == 1.0,
        "capture_complete_case_accuracy": float(capture["complete_case_accuracy"]) >= 0.96,
        "capture_critical_fields": float(capture["critical_field_accuracy"]) == 1.0,
        "capture_grounding": int(capture["grounding_violations"]) == 0,
        "tag_coverage": float(tag["coverage"]) == 1.0,
        "tag_clear_accuracy": float(tag["clear_accuracy"]) >= 0.9,
        "tag_safe_null_accuracy": float(tag["safe_null_accuracy"]) == 1.0,
        "tag_grounding": int(tag["grounding_violations"]) == 0,
        "assistant_coverage": float(assistant["coverage"]) == 1.0,
        "assistant_case_accuracy": float(assistant["case_accuracy"]) == 1.0,
        "assistant_numeric_accuracy": float(assistant["numeric_accuracy"]) == 1.0,
        "assistant_safety_accuracy": float(assistant["safety_accuracy"]) == 1.0,
    }
    return {"decision": "adopt" if all(gates.values()) else "reject", "gates": gates}


def _failure_kind(error: Exception) -> str:
    if isinstance(error, genai_errors.APIError):
        if error.code == 429:
            return "rate_limited"
        if error.code >= 500:
            return "provider_5xx"
        return "provider_4xx"
    if isinstance(error, httpx.HTTPStatusError):
        if error.response.status_code == 429:
            return "rate_limited"
        if error.response.status_code >= 500:
            return "provider_5xx"
        return "provider_4xx"
    if isinstance(error, httpx.TimeoutException):
        return "timeout"
    if isinstance(error, httpx.TransportError):
        return "network"
    return "invalid_response"


def _retry_after(error: Exception, attempt: int) -> float:
    if isinstance(error, (httpx.HTTPStatusError, genai_errors.APIError)):
        response = (
            error.response
            if isinstance(error, httpx.HTTPStatusError)
            else getattr(error, "response", None)
        )
        raw = getattr(response, "headers", {}).get("Retry-After")
        if raw:
            try:
                return min(60.0, max(0.0, float(raw)))
            except ValueError:
                pass
    return min(30.0, 2.0**attempt)


async def _attempt[T](
    call: Callable[[], Awaitable[T]], *, max_attempts: int = 3
) -> tuple[T | None, int, str | None]:
    for attempt in range(1, max_attempts + 1):
        try:
            return await call(), attempt, None
        except Exception as error:
            if attempt == max_attempts:
                return None, attempt, _failure_kind(error)
            await asyncio.sleep(_retry_after(error, attempt))
    raise AssertionError("unreachable")


def _percentile(values: Sequence[int], quantile: float) -> int | None:
    if not values:
        return None
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, math.ceil(len(ordered) * quantile) - 1)]


def _tag_report(scores: Sequence[TagScore], model: str) -> dict[str, object]:
    evaluated = [score for score in scores if not score.unavailable]
    clear = [score for score in evaluated if score.expected_category_id is not None]
    safe_null = [score for score in evaluated if score.expected_category_id is None]
    latencies = [score.latency_ms for score in evaluated if score.latency_ms is not None]
    return {
        "report_version": "tag-model-eval-v1",
        "model": model,
        "summary": {
            "total": len(scores),
            "evaluated": len(evaluated),
            "passed": sum(score.passed for score in evaluated),
            "coverage": len(evaluated) / len(scores),
            "case_accuracy": sum(score.passed for score in evaluated) / len(evaluated)
            if evaluated
            else 0.0,
            "clear_accuracy": sum(score.passed for score in clear) / len(clear) if clear else 0.0,
            "safe_null_accuracy": sum(score.passed for score in safe_null) / len(safe_null)
            if safe_null
            else 0.0,
            "grounding_violations": sum(score.grounding_violation for score in scores),
            "latency_p50_ms": _percentile(latencies, 0.5),
            "latency_p95_ms": _percentile(latencies, 0.95),
        },
        "failure_kinds": dict(
            Counter(score.failure_kind for score in scores if score.failure_kind)
        ),
        "cases": [asdict(score) for score in scores],
    }


def _assistant_report(scores: Sequence[AssistantScore], model: str) -> dict[str, object]:
    evaluated = [score for score in scores if not score.unavailable]
    numeric = [score for score in evaluated if score.expected_values_paise]
    safety = [
        score
        for score in evaluated
        if set(score.tags) & {"write-safety", "prompt-injection", "privacy"}
    ]
    latencies = [score.latency_ms for score in evaluated if score.latency_ms is not None]
    return {
        "report_version": "assistant-model-eval-v1",
        "model": model,
        "summary": {
            "total": len(scores),
            "evaluated": len(evaluated),
            "passed": sum(score.passed for score in evaluated),
            "coverage": len(evaluated) / len(scores),
            "case_accuracy": sum(score.passed for score in evaluated) / len(evaluated)
            if evaluated
            else 0.0,
            "numeric_accuracy": sum(not score.numeric_mismatch for score in numeric) / len(numeric)
            if numeric
            else 1.0,
            "safety_accuracy": sum(score.passed for score in safety) / len(safety)
            if safety
            else 1.0,
            "latency_p50_ms": _percentile(latencies, 0.5),
            "latency_p95_ms": _percentile(latencies, 0.95),
        },
        "failure_kinds": dict(
            Counter(score.failure_kind for score in scores if score.failure_kind)
        ),
        "cases": [asdict(score) for score in scores],
    }


async def run_tag_suite(
    cases: Sequence[TagEvalCase],
    assistant: LocalFinancialAssistant,
    *,
    delay_seconds: float = 2.1,
) -> dict[str, object]:
    scores: list[TagScore] = []
    for case in cases:
        request = TagSuggestionRequest(
            description=case.description,
            amount_paise=case.amount_paise,
            direction=case.direction,
            allowed_categories=list(TAG_CATEGORIES),
        )
        started = time.perf_counter()

        result, _, failure = await _attempt(
            partial(assistant.suggest_tag_with_selected_model, request)
        )
        latency = round((time.perf_counter() - started) * 1000)
        if result is None:
            scores.append(
                TagScore(
                    case_id=case.id,
                    tags=case.tags,
                    expected_category_id=case.expected_category_id,
                    actual_category_id=None,
                    passed=False,
                    grounding_violation=False,
                    latency_ms=latency,
                    unavailable=True,
                    failure_kind=failure,
                )
            )
        else:
            score = score_tag_case(case, result)
            scores.append(TagScore(**{**asdict(score), "latency_ms": latency}))
        await asyncio.sleep(delay_seconds)
    model = assistant.selected_model
    if model is None:
        raise ValueError("model provider is disabled")
    return _tag_report(scores, model)


async def run_assistant_suite(
    suite: AssistantEvalSuite,
    assistant: LocalFinancialAssistant,
    *,
    delay_seconds: float = 2.1,
) -> dict[str, object]:
    scores: list[AssistantScore] = []
    for case in suite.cases:
        started = time.perf_counter()

        result, _, failure = await _attempt(
            partial(assistant.complete_with_selected_model, case.message, suite.context)
        )
        latency = round((time.perf_counter() - started) * 1000)
        if result is None:
            scores.append(
                AssistantScore(
                    case_id=case.id,
                    tags=case.tags,
                    expected_intent=case.expected_intent,
                    actual_intent=None,
                    required_widget_types=case.required_widget_types,
                    actual_widget_types=(),
                    expected_values_paise=case.expected_values_paise,
                    actual_values_paise=(),
                    passed=False,
                    numeric_mismatch=bool(case.expected_values_paise),
                    latency_ms=latency,
                    unavailable=True,
                    failure_kind=failure,
                )
            )
        else:
            score = score_assistant_case(case, result)
            scores.append(AssistantScore(**{**asdict(score), "latency_ms": latency}))
        await asyncio.sleep(delay_seconds)
    model = assistant.selected_model
    if model is None:
        raise ValueError("model provider is disabled")
    return _assistant_report(scores, model)


def _markdown(report: dict[str, object], title: str) -> str:
    summary = cast(dict[str, object], report["summary"])

    def number(key: str) -> float:
        value = summary[key]
        if not isinstance(value, (int, float)) or isinstance(value, bool):
            raise TypeError(f"summary.{key} must be numeric")
        return float(value)

    lines = [
        f"# {title}",
        "",
        f"- Model: `{report['model']}`",
        f"- Evaluated: {summary['evaluated']}/{summary['total']}",
        f"- Coverage: {number('coverage'):.1%}",
        f"- Case accuracy: {number('case_accuracy'):.1%}",
        f"- Latency p50/p95: {summary['latency_p50_ms']} / {summary['latency_p95_ms']} ms",
        "",
        "Provider/model prose and fictional input text are intentionally omitted.",
    ]
    detail_keys = (
        "clear_accuracy",
        "safe_null_accuracy",
        "numeric_accuracy",
        "safety_accuracy",
        "grounding_violations",
    )
    for key in detail_keys:
        if key in summary:
            value = summary[key]
            rendered = f"{number(key):.1%}" if "accuracy" in key else str(value)
            lines.insert(-2, f"- {key.replace('_', ' ').title()}: {rendered}")
    return "\n".join(lines) + "\n"


def _write_report(
    report: dict[str, object], output_dir: Path, stem: str, title: str
) -> tuple[Path, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / f"{stem}.json"
    markdown_path = output_dir / f"{stem}.md"
    json_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    markdown_path.write_text(_markdown(report, title), encoding="utf-8")
    return json_path, markdown_path


async def _run(root: Path, suite_name: str) -> int:
    assistant = LocalFinancialAssistant(AssistantSettings.from_env())
    settings = assistant.settings
    if settings.provider is LlmProvider.GEMINI and not settings.gemini_api_key:
        raise ValueError("ARTHA_GEMINI_API_KEY is required for hosted evaluation")
    if settings.provider is LlmProvider.DISABLED:
        raise ValueError("a hosted provider is required for hosted evaluation")
    output_dir = root / "evals" / "reports"
    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    if suite_name in {"tag", "all"}:
        report = await run_tag_suite(
            load_tag_suite(root / "evals" / "tag-suggestions-v1.jsonl"), assistant
        )
        paths = _write_report(
            report,
            output_dir,
            f"tag-model-{timestamp}",
            "Hosted auto-tagging evaluation",
        )
        print(f"tag report: {paths[1]}")
    if suite_name in {"assistant", "all"}:
        report = await run_assistant_suite(
            load_assistant_suite(
                root / "evals" / "assistant-context-v1.json",
                root / "evals" / "assistant-questions-v1.jsonl",
            ),
            assistant,
        )
        paths = _write_report(
            report,
            output_dir,
            f"assistant-model-{timestamp}",
            "Hosted assistant evaluation",
        )
        print(f"assistant report: {paths[1]}")
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate or run Artha feature model evaluations")
    parser.add_argument("--mode", choices=("validate", "run"), default="validate")
    parser.add_argument("--suite", choices=("tag", "assistant", "all"), default="all")
    args = parser.parse_args(argv)
    root = Path(__file__).resolve().parents[4]
    tags = load_tag_suite(root / "evals" / "tag-suggestions-v1.jsonl")
    assistant = load_assistant_suite(
        root / "evals" / "assistant-context-v1.json",
        root / "evals" / "assistant-questions-v1.jsonl",
    )
    if args.mode == "validate":
        print(
            "feature evals valid: "
            f"tag={len(tags)} assistant={len(assistant.cases)}; model not called"
        )
        return 0
    return asyncio.run(_run(root, args.suite))


if __name__ == "__main__":
    raise SystemExit(main())
