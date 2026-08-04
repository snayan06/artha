from __future__ import annotations

import argparse
import asyncio
import json
from collections import Counter, defaultdict
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Protocol, cast

from pydantic import ValidationError

from artha_api.assistant import (
    AssistantSettings,
    CaptureContext,
    CaptureInterpretation,
    CaptureInterpretationResponse,
    LlmProvider,
    LocalFinancialAssistant,
)

REPORT_VERSION = "capture-model-eval-v1"
VALID_OUTCOMES = {"draft", "clarify", "reject"}
UNORDERED_LIST_FIELDS = {"member_ids", "missing"}
UNSCORED_EXPECTED_FIELDS = {"reason"}


@dataclass(frozen=True, slots=True)
class CaptureEvalCase:
    id: str
    context_id: str
    utterance: str
    outcome: str
    expected: dict[str, object]
    tags: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class CaptureEvalSuite:
    dataset_path: Path
    context_path: Path
    context_id: str
    context: CaptureContext
    cases: tuple[CaptureEvalCase, ...]


@dataclass(frozen=True, slots=True)
class FieldMismatch:
    field: str
    expected: object
    actual: object


@dataclass(frozen=True, slots=True)
class CaseScore:
    case_id: str
    tags: tuple[str, ...]
    expected_outcome: str
    actual_outcome: str | None
    provider: str | None
    model: str | None
    attempts: int
    passed: bool
    compared_fields: tuple[str, ...]
    mismatches: tuple[FieldMismatch, ...]
    actual: dict[str, object] | None


class CaptureInterpreter(Protocol):
    async def interpret_capture(
        self, message: str, context: CaptureContext
    ) -> CaptureInterpretationResponse | None: ...


def _object(value: object, *, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"{label} must be a JSON object")
    return cast(dict[str, Any], value)


def _string(value: object, *, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label} must be a non-empty string")
    return value


def _string_list(value: object, *, label: str) -> tuple[str, ...]:
    if not isinstance(value, list) or any(
        not isinstance(item, str) or not item.strip() for item in value
    ):
        raise ValueError(f"{label} must be a list of non-empty strings")
    return tuple(cast(list[str], value))


def _number(value: object, *, label: str) -> float:
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        raise TypeError(f"{label} must be numeric")
    return float(value)


def _integer(value: object, *, label: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool):
        raise TypeError(f"{label} must be an integer")
    return value


def load_capture_eval_suite(
    dataset_path: Path,
    context_path: Path,
    *,
    minimum_cases: int = 50,
) -> CaptureEvalSuite:
    context_payload = _object(
        json.loads(context_path.read_text(encoding="utf-8")), label=str(context_path)
    )
    context_id = _string(context_payload.get("id"), label="context.id")
    try:
        context = CaptureContext.model_validate(
            {key: value for key, value in context_payload.items() if key != "id"}
        )
    except ValidationError as error:
        raise ValueError(f"invalid capture context: {error}") from error

    account_ids = {account.id for account in context.accounts}
    category_ids = {category.id for category in context.categories}
    member_ids = {member.id for member in context.members}
    cases: list[CaptureEvalCase] = []
    seen_ids: set[str] = set()

    for line_number, line in enumerate(
        dataset_path.read_text(encoding="utf-8").splitlines(), start=1
    ):
        if not line.strip():
            continue
        payload = _object(json.loads(line), label=f"dataset line {line_number}")
        case_id = _string(payload.get("id"), label=f"line {line_number}.id")
        if case_id in seen_ids:
            raise ValueError(f"duplicate capture evaluation case ID: {case_id}")
        seen_ids.add(case_id)

        case_context = _string(
            payload.get("context"), label=f"{case_id}.context"
        )
        if case_context != context_id:
            raise ValueError(f"{case_id}: unknown context {case_context!r}")
        outcome = _string(payload.get("outcome"), label=f"{case_id}.outcome")
        if outcome not in VALID_OUTCOMES:
            raise ValueError(f"{case_id}: invalid outcome {outcome!r}")
        expected = _object(payload.get("expected"), label=f"{case_id}.expected")
        if not expected:
            raise ValueError(f"{case_id}: expected fields are required")
        tags = _string_list(payload.get("tags"), label=f"{case_id}.tags")
        if not tags:
            raise ValueError(f"{case_id}: at least one tag is required")

        if outcome == "draft":
            amount = expected.get("amount_paise")
            if (
                not isinstance(amount, int)
                or isinstance(amount, bool)
                or amount <= 0
            ):
                raise ValueError(f"{case_id}: amount_paise must be a positive integer")
            if expected.get("source_account_id") not in account_ids:
                raise ValueError(f"{case_id}: source account is not allow-listed")
            destination_id = expected.get("destination_account_id")
            if destination_id is not None and destination_id not in account_ids:
                raise ValueError(f"{case_id}: destination account is not allow-listed")
            if expected.get("kind") == "transfer" and (
                destination_id is None
                or destination_id == expected.get("source_account_id")
            ):
                raise ValueError(f"{case_id}: transfer accounts must be distinct")
            category_id = expected.get("category_id")
            if category_id is not None and category_id not in category_ids:
                raise ValueError(f"{case_id}: category is not allow-listed")
            expected_members = expected.get("member_ids", [])
            if not isinstance(expected_members, list) or any(
                item not in member_ids for item in expected_members
            ):
                raise ValueError(f"{case_id}: member is not allow-listed")

        cases.append(
            CaptureEvalCase(
                id=case_id,
                context_id=case_context,
                utterance=_string(
                    payload.get("utterance"), label=f"{case_id}.utterance"
                ),
                outcome=outcome,
                expected=expected,
                tags=tags,
            )
        )

    if len(cases) < minimum_cases:
        raise ValueError(
            f"capture evaluation dataset must contain at least {minimum_cases} cases"
        )
    return CaptureEvalSuite(
        dataset_path=dataset_path,
        context_path=context_path,
        context_id=context_id,
        context=context,
        cases=tuple(cases),
    )


def _normalized_value(field: str, value: object) -> object:
    if field in UNORDERED_LIST_FIELDS and isinstance(value, list):
        return sorted(value)
    return value


def _safe_actual(result: CaptureInterpretation) -> dict[str, object]:
    """Persist only constrained fields; omit all model-generated free text."""
    raw = result.model_dump(mode="json")
    allowed_fields = {
        "outcome",
        "kind",
        "amount_paise",
        "category_id",
        "source_account_id",
        "destination_account_id",
        "member_ids",
        "split_equally",
        "occurred_on",
        "missing",
    }
    return {key: value for key, value in raw.items() if key in allowed_fields}


def score_capture_case(
    case: CaptureEvalCase,
    response: CaptureInterpretationResponse | None,
    *,
    attempts: int,
) -> CaseScore:
    actual = _safe_actual(response.result) if response is not None else None
    actual_outcome = (
        cast(str, actual["outcome"])
        if actual is not None and isinstance(actual.get("outcome"), str)
        else None
    )
    compared_fields = ["outcome"]
    mismatches: list[FieldMismatch] = []
    if actual_outcome != case.outcome:
        mismatches.append(
            FieldMismatch(
                field="outcome", expected=case.outcome, actual=actual_outcome
            )
        )
    for field, expected in case.expected.items():
        if field in UNSCORED_EXPECTED_FIELDS:
            continue
        compared_fields.append(field)
        actual_value = actual.get(field) if actual is not None else None
        if _normalized_value(field, actual_value) != _normalized_value(
            field, expected
        ):
            mismatches.append(
                FieldMismatch(field=field, expected=expected, actual=actual_value)
            )

    return CaseScore(
        case_id=case.id,
        tags=case.tags,
        expected_outcome=case.outcome,
        actual_outcome=actual_outcome,
        provider=str(response.provider) if response is not None else None,
        model=response.model if response is not None else None,
        attempts=attempts,
        passed=not mismatches,
        compared_fields=tuple(compared_fields),
        mismatches=tuple(mismatches),
        actual=actual,
    )


async def evaluate_capture_suite(
    suite: CaptureEvalSuite,
    interpreter: CaptureInterpreter,
    *,
    max_attempts: int = 2,
    delay_seconds: float = 1.0,
) -> tuple[CaseScore, ...]:
    if max_attempts < 1:
        raise ValueError("max_attempts must be at least one")
    if delay_seconds < 0:
        raise ValueError("delay_seconds cannot be negative")

    scores: list[CaseScore] = []
    for index, case in enumerate(suite.cases):
        response: CaptureInterpretationResponse | None = None
        attempts = 0
        while response is None and attempts < max_attempts:
            attempts += 1
            response = await interpreter.interpret_capture(case.utterance, suite.context)
            if response is None and attempts < max_attempts:
                await asyncio.sleep(delay_seconds)
        scores.append(score_capture_case(case, response, attempts=attempts))
        if delay_seconds and index < len(suite.cases) - 1:
            await asyncio.sleep(delay_seconds)
    return tuple(scores)


def _slice(scores: Sequence[CaseScore]) -> dict[str, object]:
    passed = sum(score.passed for score in scores)
    total = len(scores)
    return {
        "total": total,
        "passed": passed,
        "failed": total - passed,
        "pass_rate": passed / total if total else 0.0,
    }


def build_evaluation_report(
    suite: CaptureEvalSuite,
    scores: Sequence[CaseScore],
    *,
    started_at: datetime,
    finished_at: datetime,
) -> dict[str, object]:
    field_totals: Counter[str] = Counter()
    field_failures: Counter[str] = Counter()
    outcome_scores: dict[str, list[CaseScore]] = defaultdict(list)
    tag_scores: dict[str, list[CaseScore]] = defaultdict(list)
    providers: Counter[str] = Counter()
    models: Counter[str] = Counter()

    for score in scores:
        for field in score.compared_fields:
            field_totals[field] += 1
        for mismatch in score.mismatches:
            field_failures[mismatch.field] += 1
        outcome_scores[score.expected_outcome].append(score)
        for tag in score.tags:
            tag_scores[tag].append(score)
        if score.provider:
            providers[score.provider] += 1
        if score.model:
            models[score.model] += 1

    field_slices = {
        field: {
            "total": total,
            "passed": total - field_failures[field],
            "failed": field_failures[field],
            "pass_rate": (total - field_failures[field]) / total,
        }
        for field, total in sorted(field_totals.items())
    }
    failures = [
        {
            "case_id": score.case_id,
            "tags": list(score.tags),
            "expected_outcome": score.expected_outcome,
            "actual_outcome": score.actual_outcome,
            "attempts": score.attempts,
            "mismatches": [
                {
                    "field": mismatch.field,
                    "expected": mismatch.expected,
                    "actual": mismatch.actual,
                }
                for mismatch in score.mismatches
            ],
            "actual": score.actual,
        }
        for score in scores
        if not score.passed
    ]
    compared_fields = sum(field_totals.values())
    failed_fields = sum(field_failures.values())
    return {
        "report_version": REPORT_VERSION,
        "mode": "model",
        "started_at": started_at.astimezone(UTC).isoformat(),
        "finished_at": finished_at.astimezone(UTC).isoformat(),
        "dataset": suite.dataset_path.name,
        "context": suite.context_id,
        "summary": {
            **_slice(scores),
            "compared_fields": compared_fields,
            "failed_fields": failed_fields,
            "field_pass_rate": (
                (compared_fields - failed_fields) / compared_fields
                if compared_fields
                else 0.0
            ),
            "provider_unavailable_cases": sum(
                score.actual_outcome is None for score in scores
            ),
        },
        "providers": dict(sorted(providers.items())),
        "models": dict(sorted(models.items())),
        "outcome_slices": {
            key: _slice(value) for key, value in sorted(outcome_scores.items())
        },
        "field_slices": field_slices,
        "tag_slices": {
            key: _slice(value) for key, value in sorted(tag_scores.items())
        },
        "failures": failures,
    }


def build_validation_report(suite: CaptureEvalSuite) -> dict[str, object]:
    outcomes = Counter(case.outcome for case in suite.cases)
    tags = Counter(tag for case in suite.cases for tag in case.tags)
    return {
        "report_version": REPORT_VERSION,
        "mode": "validation",
        "status": "valid",
        "dataset": suite.dataset_path.name,
        "context": suite.context_id,
        "total_cases": len(suite.cases),
        "outcomes": dict(sorted(outcomes.items())),
        "tags": dict(sorted(tags.items())),
        "failures": [],
    }


def render_evaluation_markdown(report: dict[str, object]) -> str:
    if report.get("mode") == "validation":
        return (
            "# Capture evaluation validation\n\n"
            f"- Dataset: `{report['dataset']}`\n"
            f"- Context: `{report['context']}`\n"
            f"- Cases: {report['total_cases']}\n"
            "- Status: valid\n\n"
            "No model was called and no credential was required.\n"
        )

    summary = cast(dict[str, object], report["summary"])
    outcome_slices = cast(dict[str, dict[str, object]], report["outcome_slices"])
    field_slices = cast(dict[str, dict[str, object]], report["field_slices"])
    tag_slices = cast(dict[str, dict[str, object]], report["tag_slices"])
    failures = cast(list[dict[str, object]], report["failures"])
    lines = [
        "# Hosted capture model evaluation",
        "",
        f"- Dataset: `{report['dataset']}`",
        f"- Context: `{report['context']}`",
        f"- Cases passed: {summary['passed']}/{summary['total']}",
        f"- Case pass rate: {_number(summary['pass_rate'], label='pass_rate'):.1%}",
        "- Structured-field pass rate: "
        f"{_number(summary['field_pass_rate'], label='field_pass_rate'):.1%}",
        f"- Provider-unavailable cases: {summary['provider_unavailable_cases']}",
        "",
        "## Outcome slices",
        "",
        "| Expected outcome | Passed | Total | Pass rate |",
        "| --- | ---: | ---: | ---: |",
    ]
    for outcome, item in outcome_slices.items():
        lines.append(
            f"| {outcome} | {item['passed']} | {item['total']} | "
            f"{_number(item['pass_rate'], label='outcome pass_rate'):.1%} |"
        )
    lines.extend(
        [
            "",
            "## Structured-field slices",
            "",
            "| Field | Passed | Total | Pass rate |",
            "| --- | ---: | ---: | ---: |",
        ]
    )
    for field, item in field_slices.items():
        lines.append(
            f"| {field} | {item['passed']} | {item['total']} | "
            f"{_number(item['pass_rate'], label='field pass_rate'):.1%} |"
        )

    failing_tags = [
        (tag, item)
        for tag, item in tag_slices.items()
        if _integer(item["failed"], label="tag failed") > 0
    ]
    lines.extend(
        [
            "",
            "## Failing tag slices",
            "",
            "| Tag | Failed | Total | Pass rate |",
            "| --- | ---: | ---: | ---: |",
        ]
    )
    if failing_tags:
        for tag, item in failing_tags:
            lines.append(
                f"| {tag} | {item['failed']} | {item['total']} | "
                f"{_number(item['pass_rate'], label='tag pass_rate'):.1%} |"
            )
    else:
        lines.append("| None | 0 | 0 | 100.0% |")

    lines.extend(
        [
            "",
            "## Failed cases",
            "",
            "Free-text utterances and model explanations are intentionally omitted.",
            "",
            "| Case | Tags | Mismatched fields | Actual outcome |",
            "| --- | --- | --- | --- |",
        ]
    )
    if failures:
        for failure in failures:
            mismatches = cast(list[dict[str, object]], failure["mismatches"])
            fields = ", ".join(str(item["field"]) for item in mismatches)
            tags = ", ".join(cast(list[str], failure["tags"]))
            lines.append(
                f"| {failure['case_id']} | {tags} | {fields} | "
                f"{failure['actual_outcome'] or 'unavailable'} |"
            )
    else:
        lines.append("| None | - | - | - |")
    lines.append("")
    return "\n".join(lines)


def write_reports(
    report: dict[str, object], output_dir: Path, *, stem: str
) -> tuple[Path, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / f"{stem}.json"
    markdown_path = output_dir / f"{stem}.md"
    json_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    markdown_path.write_text(render_evaluation_markdown(report), encoding="utf-8")
    return json_path, markdown_path


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[4]


def _display_path(path: Path, root: Path) -> str:
    try:
        return str(path.relative_to(root))
    except ValueError:
        return path.name


def _parser() -> argparse.ArgumentParser:
    root = _repo_root()
    parser = argparse.ArgumentParser(
        description="Validate or run Artha's fictional capture-model benchmark."
    )
    parser.add_argument("--mode", choices=("validate", "run"), default="validate")
    parser.add_argument(
        "--output-dir", type=Path, default=root / "evals" / "reports"
    )
    parser.add_argument("--attempts", type=int, default=2)
    parser.add_argument("--delay-seconds", type=float, default=1.0)
    parser.add_argument("--minimum-pass-rate", type=float, default=1.0)
    return parser


async def _run_model_evaluation(
    suite: CaptureEvalSuite,
    *,
    max_attempts: int,
    delay_seconds: float,
) -> dict[str, object]:
    settings = AssistantSettings.from_env()
    if settings.provider is LlmProvider.DISABLED:
        raise RuntimeError(
            "capture model is disabled; configure the server-side provider or use --mode validate"
        )
    if settings.provider is LlmProvider.GROQ and not settings.groq_api_key:
        raise RuntimeError(
            "Groq is selected but its server-side key is missing; use --mode validate"
        )
    assistant = LocalFinancialAssistant(settings)
    started_at = datetime.now(UTC)
    scores = await evaluate_capture_suite(
        suite,
        assistant,
        max_attempts=max_attempts,
        delay_seconds=delay_seconds,
    )
    return build_evaluation_report(
        suite, scores, started_at=started_at, finished_at=datetime.now(UTC)
    )


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    root = _repo_root()
    try:
        suite = load_capture_eval_suite(
            root / "evals" / "capture-parser-v1.jsonl",
            root / "evals" / "capture-context-v1.json",
        )
        if args.mode == "validate":
            report = build_validation_report(suite)
            stem = "capture-validation"
        else:
            if not 0 <= args.minimum_pass_rate <= 1:
                raise ValueError("minimum-pass-rate must be between zero and one")
            report = asyncio.run(
                _run_model_evaluation(
                    suite,
                    max_attempts=args.attempts,
                    delay_seconds=args.delay_seconds,
                )
            )
            timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
            stem = f"capture-model-{timestamp}"
        json_path, markdown_path = write_reports(
            report, args.output_dir, stem=stem
        )
    except (OSError, ValueError, RuntimeError, json.JSONDecodeError) as error:
        print(f"capture eval failed: {error}")
        return 2

    if args.mode == "validate":
        print(f"capture evals: {len(suite.cases)} cases valid; model not called")
        print(
            "reports: "
            f"{_display_path(json_path, root)} and "
            f"{_display_path(markdown_path, root)}"
        )
        return 0

    summary = cast(dict[str, object], report["summary"])
    pass_rate = _number(summary["pass_rate"], label="pass_rate")
    print(f"capture model eval: {summary['passed']}/{summary['total']} cases passed")
    print(
        "reports: "
        f"{_display_path(json_path, root)} and "
        f"{_display_path(markdown_path, root)}"
    )
    return 0 if pass_rate >= args.minimum_pass_rate else 1


if __name__ == "__main__":
    raise SystemExit(main())
