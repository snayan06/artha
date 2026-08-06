from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from artha_api.assistant import (
    ASSISTANT_INTENT_MESSAGES,
    AssistantCompletion,
    AssistantIntent,
    AssistantSettings,
    LlmProvider,
    LocalFinancialAssistant,
    MetricWidget,
    TagSuggestion,
)
from artha_api.feature_evals import (
    AssistantEvalCase,
    TagEvalCase,
    build_decision,
    load_assistant_suite,
    load_tag_suite,
    main,
    run_tag_suite,
    score_assistant_case,
    score_tag_case,
)

ROOT = Path(__file__).resolve().parents[3]


def test_versioned_feature_datasets_are_valid_and_diverse() -> None:
    tag_suite = load_tag_suite(ROOT / "evals" / "tag-suggestions-v1.jsonl")
    assistant_suite = load_assistant_suite(
        ROOT / "evals" / "assistant-context-v1.json",
        ROOT / "evals" / "assistant-questions-v1.jsonl",
    )

    assert len(tag_suite) >= 30
    assert len(assistant_suite.cases) >= 24
    assert {case.expected_category_id for case in tag_suite} >= {None, "food", "transport"}
    assert {case.expected_intent for case in assistant_suite.cases} >= {
        "summary",
        "spending",
        "income",
        "shared",
        "transactions",
        "clarification",
        "unsupported",
    }


@pytest.mark.asyncio
async def test_hosted_tag_benchmark_dispatches_to_selected_gemini_model() -> None:
    calls: list[dict[str, object]] = []
    suggestion = {
        "category_id": "food",
        "category_name": "Food",
        "confidence": 0.95,
        "reason": "The fictional merchant is a restaurant.",
    }

    class Interactions:
        async def create(self, **body: object) -> SimpleNamespace:
            calls.append(body)
            return SimpleNamespace(output_text=json.dumps(suggestion))

    gemini = SimpleNamespace(
        aio=SimpleNamespace(
            interactions=Interactions(),
            models=SimpleNamespace(),
        )
    )

    assistant = LocalFinancialAssistant(
        AssistantSettings(
            provider=LlmProvider.GEMINI,
            gemini_api_key="gemini-test-key",
        ),
        gemini_client=gemini,
    )
    report = await run_tag_suite(
        [
            TagEvalCase(
                id="TAG-GEMINI",
                description="Fictional restaurant",
                amount_paise=10_000,
                direction="expense",
                expected_category_id="food",
                tags=("clear",),
            )
        ],
        assistant,
        delay_seconds=0,
    )

    assert len(calls) == 1
    assert calls[0]["model"] == "gemini-3.5-flash-lite"
    assert report["model"] == "gemini-3.5-flash-lite"
    assert report["summary"]["case_accuracy"] == 1.0


def test_hosted_feature_eval_requires_gemini_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ARTHA_LLM_PROVIDER", "gemini")
    monkeypatch.delenv("ARTHA_GEMINI_API_KEY", raising=False)

    with pytest.raises(
        ValueError, match="ARTHA_GEMINI_API_KEY is required for hosted evaluation"
    ):
        main(["--mode", "run", "--suite", "tag"])


def test_tag_scoring_distinguishes_correct_null_and_invented_category() -> None:
    clear = TagEvalCase(
        id="TAG-001",
        description="Fictional restaurant",
        amount_paise=10_000,
        direction="expense",
        expected_category_id="food",
        tags=("clear",),
    )
    unknown = TagEvalCase(
        id="TAG-002",
        description="Unknown merchant",
        amount_paise=20_000,
        direction="expense",
        expected_category_id=None,
        tags=("unknown",),
    )

    correct = score_tag_case(
        clear,
        TagSuggestion(
            category_id="food",
            category_name="Food",
            confidence=0.9,
            reason="Fictional fixture",
        ),
    )
    safe_null = score_tag_case(
        unknown,
        TagSuggestion(
            category_id=None,
            category_name=None,
            confidence=0.1,
            reason="Insufficient evidence",
        ),
    )
    invented = score_tag_case(
        unknown,
        TagSuggestion(
            category_id="invented",
            category_name="Invented",
            confidence=1.0,
            reason="Unsafe",
        ),
    )

    assert correct.passed is True
    assert safe_null.passed is True
    assert invented.passed is False
    assert invented.grounding_violation is True


def test_assistant_scoring_checks_intent_widget_and_financial_values() -> None:
    case = AssistantEvalCase(
        id="AST-001",
        message="Show balance",
        expected_intent="summary",
        required_widget_types=("metric",),
        expected_values_paise=(1_500_000,),
        tags=("summary",),
    )
    correct = AssistantCompletion(
        message=ASSISTANT_INTENT_MESSAGES[AssistantIntent.SUMMARY],
        intent=AssistantIntent.SUMMARY,
        widgets=[
            MetricWidget(
                type="metric",
                title="Balance",
                value_paise=1_500_000,
            )
        ],
    )
    wrong_number = AssistantCompletion(
        message=ASSISTANT_INTENT_MESSAGES[AssistantIntent.SUMMARY],
        intent=AssistantIntent.SUMMARY,
        widgets=[MetricWidget(type="metric", title="Balance", value_paise=1_400_000)],
    )

    assert score_assistant_case(case, correct).passed is True
    wrong = score_assistant_case(case, wrong_number)
    assert wrong.passed is False
    assert wrong.numeric_mismatch is True


@pytest.mark.parametrize(
    "message",
    ["Your available balance is 15000.", "Your balance is ९९ crore.", "INR one hundred."],
)
def test_assistant_eval_rejects_unsafe_prose_before_scoring(message: str) -> None:
    # Schema validation rejects unsafe model prose before the scoring layer receives it.
    with pytest.raises(ValidationError):
        AssistantCompletion(
            message=message,
            intent=AssistantIntent.SUMMARY,
            widgets=[
                MetricWidget(
                    type="metric",
                    title="Balance",
                    value_paise=1_500_000,
                )
            ],
        )


@pytest.mark.parametrize(
    ("intent", "message"),
    [
        (AssistantIntent.SUMMARY, "Here is your spending overview."),
        (AssistantIntent.SUMMARY, "  Here is your current account overview.  "),
        (AssistantIntent.SUMMARY, "Your balance is a grand."),
        (AssistantIntent.INCOME, "This benign arbitrary sentence is not approved."),
    ],
)
def test_assistant_eval_rejects_unapproved_intent_narrative_before_scoring(
    intent: AssistantIntent,
    message: str,
) -> None:
    with pytest.raises(ValidationError):
        AssistantCompletion(
            message=message,
            intent=intent,
            widgets=[
                MetricWidget(
                    type="metric",
                    title="Balance",
                    value_paise=1_500_000,
                )
            ],
        )


def test_decision_rejects_any_safety_failure_and_requires_full_coverage() -> None:
    passing = {
        "capture": {
            "coverage": 1.0,
            "complete_case_accuracy": 0.98,
            "critical_field_accuracy": 1.0,
            "grounding_violations": 0,
        },
        "tag": {
            "coverage": 1.0,
            "clear_accuracy": 0.95,
            "safe_null_accuracy": 1.0,
            "grounding_violations": 0,
        },
        "assistant": {
            "coverage": 1.0,
            "case_accuracy": 1.0,
            "numeric_accuracy": 1.0,
            "safety_accuracy": 1.0,
        },
    }

    assert build_decision(passing)["decision"] == "adopt"
    failing = json.loads(json.dumps(passing))
    failing["tag"]["grounding_violations"] = 1
    assert build_decision(failing)["decision"] == "reject"
    incomplete = json.loads(json.dumps(passing))
    incomplete["assistant"]["coverage"] = 0.95
    assert build_decision(incomplete)["decision"] == "reject"
