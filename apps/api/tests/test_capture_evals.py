from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from artha_api.assistant import (
    CaptureDraftInterpretation,
    CaptureInterpretationResponse,
    LlmProvider,
)
from artha_api.capture_evals import (
    CaptureEvalCase,
    CaptureInterpreter,
    build_evaluation_report,
    build_validation_report,
    evaluate_capture_suite,
    load_capture_eval_suite,
    main,
    render_evaluation_markdown,
    score_capture_case,
    write_reports,
)

ROOT = Path(__file__).resolve().parents[3]


def _suite():
    return load_capture_eval_suite(
        ROOT / "evals" / "capture-parser-v1.jsonl",
        ROOT / "evals" / "capture-context-v1.json",
    )


def _response(**updates: object) -> CaptureInterpretationResponse:
    payload: dict[str, object] = {
        "outcome": "draft",
        "kind": "transfer",
        "amount_paise": 2_500_000,
        "description": "Model free text must not be persisted",
        "category_id": None,
        "category_name": None,
        "source_account_id": "acct-icici-bank",
        "destination_account_id": "acct-hdfc-upi",
        "member_ids": [],
        "split_equally": False,
        "occurred_on": None,
        "confidence": 0.98,
        "warnings": ["Model free text must not be persisted"],
    }
    payload.update(updates)
    return CaptureInterpretationResponse(
        provider=LlmProvider.GROQ,
        model="test-model",
        result=CaptureDraftInterpretation.model_validate(payload),
    )


def test_versioned_suite_loads_and_validates_without_a_provider() -> None:
    suite = _suite()
    report = build_validation_report(suite)

    assert len(suite.cases) == 50
    assert report["mode"] == "validation"
    assert report["total_cases"] == 50
    assert report["failures"] == []


def test_scoring_compares_structured_subset_and_omits_free_text() -> None:
    case = CaptureEvalCase(
        id="CAP-TEST",
        context_id="standard-household",
        utterance="fictional input",
        outcome="draft",
        expected={
            "kind": "transfer",
            "amount_paise": 2_500_000,
            "source_account_id": "acct-icici-bank",
            "destination_account_id": "acct-hdfc-upi",
        },
        tags=("transfer",),
    )

    score = score_capture_case(case, _response(), attempts=1)

    assert score.passed is True
    assert score.actual is not None
    assert "description" not in score.actual
    assert "warnings" not in score.actual
    assert "confidence" not in score.actual


def test_scoring_reports_field_and_outcome_mismatches() -> None:
    field_case = CaptureEvalCase(
        id="CAP-FIELD",
        context_id="standard-household",
        utterance="fictional input",
        outcome="draft",
        expected={"kind": "transfer", "amount_paise": 2_500_000},
        tags=("transfer", "amount"),
    )
    field_score = score_capture_case(
        field_case, _response(amount_paise=250_000), attempts=1
    )
    unavailable_score = score_capture_case(field_case, None, attempts=2)

    assert field_score.passed is False
    assert [item.field for item in field_score.mismatches] == ["amount_paise"]
    assert unavailable_score.actual_outcome is None
    assert [item.field for item in unavailable_score.mismatches] == [
        "outcome",
        "kind",
        "amount_paise",
    ]


class _RetryingInterpreter(CaptureInterpreter):
    def __init__(self) -> None:
        self.calls = 0

    async def interpret_capture(self, message, context):  # type: ignore[no-untyped-def]
        del message, context
        self.calls += 1
        return None if self.calls == 1 else _response()


@pytest.mark.asyncio
async def test_evaluator_retries_adapter_unavailability_without_logging_payload() -> None:
    suite = _suite()
    one_case_suite = type(suite)(
        dataset_path=suite.dataset_path,
        context_path=suite.context_path,
        context_id=suite.context_id,
        context=suite.context,
        cases=(suite.cases[0],),
    )
    interpreter = _RetryingInterpreter()

    scores = await evaluate_capture_suite(
        one_case_suite, interpreter, max_attempts=2, delay_seconds=0
    )

    assert interpreter.calls == 2
    assert scores[0].passed is True
    assert scores[0].attempts == 2


def test_reports_include_error_slices_and_exclude_utterances(tmp_path: Path) -> None:
    suite = _suite()
    case = suite.cases[0]
    score = score_capture_case(case, _response(amount_paise=25_000), attempts=1)
    report = build_evaluation_report(
        suite,
        [score],
        started_at=datetime(2026, 8, 5, tzinfo=UTC),
        finished_at=datetime(2026, 8, 5, 0, 0, 1, tzinfo=UTC),
    )
    json_path, markdown_path = write_reports(report, tmp_path, stem="report")
    machine = json.loads(json_path.read_text(encoding="utf-8"))
    human = markdown_path.read_text(encoding="utf-8")

    assert machine["field_slices"]["amount_paise"]["failed"] == 1
    assert machine["tag_slices"]["transfer"]["failed"] == 1
    assert machine["failures"][0]["case_id"] == "CAP-001"
    assert case.utterance not in json_path.read_text(encoding="utf-8")
    assert case.utterance not in human
    assert "Mismatched fields" in human
    assert "amount_paise" in human


def test_validation_markdown_states_that_no_model_was_called() -> None:
    markdown = render_evaluation_markdown(build_validation_report(_suite()))

    assert "No model was called" in markdown
    assert "50" in markdown


def test_run_mode_fails_closed_without_a_provider_key(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setenv("ARTHA_LLM_PROVIDER", "groq")
    monkeypatch.delenv("ARTHA_GROQ_API_KEY", raising=False)

    exit_code = main(
        [
            "--mode",
            "run",
            "--output-dir",
            str(tmp_path),
        ]
    )

    output = capsys.readouterr().out
    assert exit_code == 2
    assert "server-side key is missing" in output
    assert not list(tmp_path.iterdir())
