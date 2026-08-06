from __future__ import annotations

import json
from types import SimpleNamespace

import httpx
import pytest
from pydantic import ValidationError

from artha_api.assistant import (
    ASSISTANT_INTENT_MESSAGES,
    AssistantCompletion,
    AssistantFinancialContext,
    AssistantIntent,
    AssistantSettings,
    AssistantUnavailableError,
    CaptureAccount,
    CaptureCategory,
    CaptureContext,
    CaptureFailureKind,
    CaptureInterpretationError,
    ContextCategory,
    ContextMemberBalance,
    ContextMonth,
    ContextTransaction,
    LlmProvider,
    LocalFinancialAssistant,
    MetricWidget,
    TagCategory,
    TagSuggestionRequest,
)


class FakeGeminiInteractions:
    def __init__(self, output_text: str) -> None:
        self.output_text = output_text
        self.calls: list[dict[str, object]] = []

    async def create(self, **body: object) -> SimpleNamespace:
        self.calls.append(body)
        return SimpleNamespace(output_text=self.output_text, status="completed")


class FakeGeminiModels:
    def __init__(self) -> None:
        self.requested: list[str] = []

    async def get(self, *, model: str) -> SimpleNamespace:
        self.requested.append(model)
        return SimpleNamespace(name=model)


class FakeGeminiClient:
    def __init__(self, output_text: str) -> None:
        self.aio = SimpleNamespace(
            interactions=FakeGeminiInteractions(output_text),
            models=FakeGeminiModels(),
        )


def test_groq_provider_is_rejected_as_unsupported(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ARTHA_LLM_PROVIDER", "groq")

    with pytest.raises(ValueError, match="unsupported LLM provider: groq"):
        AssistantSettings.from_env()


def test_legacy_groq_key_does_not_auto_select_provider(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("ARTHA_LLM_PROVIDER", raising=False)
    monkeypatch.delenv("ARTHA_GEMINI_API_KEY", raising=False)
    monkeypatch.setenv("ARTHA_GROQ_API_KEY", "legacy-key")

    assert AssistantSettings.from_env().provider is LlmProvider.DISABLED


def test_gemini_defaults_to_flash_lite_and_wins_auto_detection(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("ARTHA_LLM_PROVIDER", raising=False)
    monkeypatch.setenv("ARTHA_GEMINI_API_KEY", "gemini-test-key")
    monkeypatch.delenv("ARTHA_GEMINI_MODEL", raising=False)

    direct = AssistantSettings(
        provider=LlmProvider.GEMINI, gemini_api_key="gemini-test-key"
    )
    from_env = AssistantSettings.from_env()

    assert direct.gemini_model == "gemini-3.5-flash-lite"
    assert from_env.provider is LlmProvider.GEMINI
    assert from_env.gemini_model == "gemini-3.5-flash-lite"
    assert "gemini-test-key" not in repr(direct)


def test_explicit_ollama_selection_remains_supported(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ARTHA_LLM_PROVIDER", "ollama")
    monkeypatch.delenv("ARTHA_GEMINI_API_KEY", raising=False)

    assert AssistantSettings.from_env().provider is LlmProvider.OLLAMA


@pytest.fixture
def financial_context() -> AssistantFinancialContext:
    return AssistantFinancialContext(
        total_balance_paise=1_500_000,
        current_month_spend_paise=250_000,
        current_month_income_paise=800_000,
        member_balances=[
            ContextMemberBalance(member_name="Avery", balance_paise=40_000)
        ],
        top_categories=[ContextCategory(category="Food", amount_paise=120_000)],
        monthly=[ContextMonth(month="Aug", income_paise=800_000, spend_paise=250_000)],
        recent_transactions=[
            ContextTransaction(
                occurred_on="2026-08-04",
                kind="expense",
                personal_share_paise=42_000,
                category="Food",
            )
        ],
    )


@pytest.mark.parametrize(
    "message",
    [
        pytest.param(None, id="missing"),
        pytest.param("   \n\t", id="blank"),
        pytest.param("x" * 401, id="too-long"),
    ],
)
def test_assistant_completion_requires_a_nonblank_bounded_model_message(
    message: str | None,
) -> None:
    payload: dict[str, object] = {
        "intent": AssistantIntent.SUMMARY,
        "widgets": [
            MetricWidget(
                type="metric",
                title="Available balance",
                value_paise=1_500_000,
            )
        ],
    }
    if message is not None:
        payload["message"] = message

    with pytest.raises(ValidationError):
        AssistantCompletion.model_validate(payload)


def test_assistant_completion_keeps_the_400_character_schema_bound() -> None:
    assert AssistantCompletion.model_json_schema()["properties"]["message"]["maxLength"] == 400


def test_assistant_completion_schema_advertises_only_approved_messages() -> None:
    message_schema = AssistantCompletion.model_json_schema()["properties"]["message"]

    assert set(message_schema["enum"]) == {
        "Here is your current account overview.",
        "Here is your spending overview.",
        "Here is your income overview.",
        "Here is your cash-flow overview.",
        "Here are your shared balances.",
        "Here is your recent ledger activity.",
        "I need a little more detail to answer that.",
        "I can only help with read-only ledger questions.",
    }


def test_assistant_completion_schema_rejects_the_ungrounded_insight_channel() -> None:
    with pytest.raises(ValidationError):
        AssistantCompletion.model_validate(
            {
                "message": ASSISTANT_INTENT_MESSAGES[AssistantIntent.SUMMARY],
                "intent": "summary",
                "widgets": [
                    {
                        "type": "insight",
                        "title": "Model narrative",
                        "body": "An arbitrary second narrative channel.",
                    }
                ],
            }
        )


@pytest.mark.parametrize(
    "message",
    [
        "Your balance is 99 crore.",
        "Your balance is ninety nine crore.",
        "Your balance is ninety-nine crore.",
        "Your balance is ९९ crore.",
        "Your balance is a dollar.",
        "Your balance is a euro.",
        "Your balance is a grand.",
        "The weather outside is pleasant.",
        "Your balance is one lakh rupees.",
        "Your savings rate is fifty percent.",
        "INR one hundred is shown below.",
        "Your balance is ₹crore.",
        "Your balance is $high.",
        "Your balance is €high.",
        "Your balance is £high.",
        "Your savings rate is %high.",
    ],
)
def test_assistant_completion_rejects_unapproved_narrative(
    message: str,
) -> None:
    with pytest.raises(ValidationError):
        AssistantCompletion(
            message=message,
            intent=AssistantIntent.SUMMARY,
            widgets=[
                MetricWidget(
                    type="metric",
                    title="Available balance",
                    value_paise=1_500_000,
                )
            ],
        )


@pytest.mark.parametrize(("intent", "message"), ASSISTANT_INTENT_MESSAGES.items())
def test_assistant_completion_accepts_only_the_message_for_its_intent(
    intent: AssistantIntent,
    message: str,
) -> None:
    completion = AssistantCompletion(
        message=message,
        intent=intent,
        widgets=[
            MetricWidget(
                type="metric",
                title="Available balance",
                value_paise=1_500_000,
            )
        ],
    )

    assert completion.message == message


def test_every_assistant_intent_has_one_approved_message() -> None:
    assert set(ASSISTANT_INTENT_MESSAGES) == set(AssistantIntent)


@pytest.mark.asyncio
async def test_disabled_assistant_is_unavailable(
    financial_context: AssistantFinancialContext,
) -> None:
    assistant = LocalFinancialAssistant(AssistantSettings(provider=LlmProvider.DISABLED))

    status = await assistant.status()
    assert status.model_dump() == {
        "configured": False,
        "provider": "disabled",
        "model": None,
        "available": False,
        "active_provider": None,
        "ollama_fallback_enabled": False,
        "detail": "disabled",
    }
    with pytest.raises(
        AssistantUnavailableError, match="AI assistant is unavailable"
    ):
        await assistant.chat("How much did I spend?", financial_context)


@pytest.mark.asyncio
async def test_gemini_uses_private_stateless_structured_output(
    financial_context: AssistantFinancialContext,
) -> None:
    completion = {
        "message": ASSISTANT_INTENT_MESSAGES[AssistantIntent.SPENDING],
        "intent": "spending",
        "widgets": [
            {
                "type": "metric",
                "title": "Spending this month",
                "value_paise": 250000,
                "caption": None,
                "tone": "neutral",
            }
        ],
    }
    gemini = FakeGeminiClient(json.dumps(completion))

    assistant = LocalFinancialAssistant(
        AssistantSettings(
            provider=LlmProvider.GEMINI, gemini_api_key="gemini-test-key"
        ),
        gemini_client=gemini,
    )
    response = await assistant.chat("Show spending", financial_context)

    assert response.mode == "model"
    assert response.provider == "gemini"
    assert response.result.message == ASSISTANT_INTENT_MESSAGES[AssistantIntent.SPENDING]
    body = gemini.aio.interactions.calls[0]
    assert body["model"] == "gemini-3.5-flash-lite"
    assert body["store"] is False
    assert body["generation_config"]["thinking_level"] == "minimal"
    assert body["response_format"]["mime_type"] == "application/json"
    assert "schema" not in body["response_format"]
    assert "intent=unsupported" in body["system_instruction"]
    normalized_prompt = " ".join(body["system_instruction"].casefold().split())
    assert "top spending categories must use a chart" in normalized_prompt
    assert "cashflow comparison must use a chart" in normalized_prompt
    assert "return exactly its approved message" in normalized_prompt
    assert "financial numbers only in allow-listed widgets" in normalized_prompt
    for intent, message in ASSISTANT_INTENT_MESSAGES.items():
        assert f'intent={intent.value}: message="{message.casefold()}"' in normalized_prompt
    assert "tools" not in body


@pytest.mark.parametrize(
    "widget",
    [
        {"type": "metric", "title": "Invented", "value_paise": 999_999},
        {
            "type": "chart",
            "title": "Categories",
            "chart_type": "bar",
            "points": [{"label": "Invented", "value_paise": 120_000}],
        },
        {
            "type": "chart",
            "title": "Categories",
            "chart_type": "bar",
            "points": [{"label": "Food", "value_paise": 999_999}],
        },
        {
            "type": "table",
            "title": "Activity",
            "rows": [
                {
                    "label": "Invented",
                    "amount_paise": 42_000,
                    "date": "2026-08-04",
                    "kind": "expense",
                }
            ],
        },
        {
            "type": "table",
            "title": "Activity",
            "rows": [
                {
                    "label": "Food",
                    "amount_paise": 999_999,
                    "date": "2026-08-04",
                    "kind": "expense",
                }
            ],
        },
    ],
)
@pytest.mark.asyncio
async def test_chat_rejects_ungrounded_model_widgets(
    widget: dict[str, object],
    financial_context: AssistantFinancialContext,
) -> None:
    completion = {
        "message": ASSISTANT_INTENT_MESSAGES[AssistantIntent.SUMMARY],
        "intent": "summary",
        "widgets": [widget],
    }
    assistant = LocalFinancialAssistant(
        AssistantSettings(
            provider=LlmProvider.GEMINI,
            gemini_api_key="gemini-test-key",
        ),
        gemini_client=FakeGeminiClient(json.dumps(completion)),
    )

    with pytest.raises(AssistantUnavailableError, match="AI assistant is unavailable"):
        await assistant.chat("Show my ledger", financial_context)


@pytest.mark.parametrize(
    "widget",
    [
        {"type": "metric", "title": "Balance", "value_paise": 1_500_000},
        {
            "type": "chart",
            "title": "Grounded chart",
            "chart_type": "bar",
            "points": [
                {"label": "Food", "value_paise": 120_000},
                {"label": "Aug", "value_paise": 800_000},
            ],
        },
        {
            "type": "table",
            "title": "Grounded table",
            "rows": [
                {"label": "Avery", "amount_paise": 40_000},
                {
                    "label": "Food",
                    "amount_paise": 42_000,
                    "date": "2026-08-04",
                    "kind": "expense",
                },
            ],
        },
    ],
)
@pytest.mark.asyncio
async def test_chat_accepts_server_grounded_model_widgets(
    widget: dict[str, object],
    financial_context: AssistantFinancialContext,
) -> None:
    completion = {
        "message": ASSISTANT_INTENT_MESSAGES[AssistantIntent.SUMMARY],
        "intent": "summary",
        "widgets": [widget],
    }
    assistant = LocalFinancialAssistant(
        AssistantSettings(
            provider=LlmProvider.GEMINI,
            gemini_api_key="gemini-test-key",
        ),
        gemini_client=FakeGeminiClient(json.dumps(completion)),
    )

    response = await assistant.chat("Show my ledger", financial_context)

    assert response.result.widgets[0].model_dump(mode="json", exclude_defaults=True) == widget


@pytest.mark.asyncio
async def test_gemini_capture_interpretation_resolves_25k_transfer() -> None:
    context = CaptureContext(
        today="2026-08-04",
        timezone="Asia/Kolkata",
        accounts=[
            CaptureAccount(id="icici-id", name="ICICI Bank", kind="bank"),
            CaptureAccount(id="hdfc-id", name="HDFC Bank", kind="bank"),
        ],
        categories=[CaptureCategory(id="other-id", name="Other", kind="both")],
    )

    interpretation = {
        "outcome": "draft",
        "kind": "transfer",
        "amount_paise": 2_500_000,
        "description": "Self transfer",
        "category_id": None,
        "category_name": None,
        "source_account_id": "icici-id",
        "destination_account_id": "hdfc-id",
        "member_ids": [],
        "split_equally": False,
        "occurred_on": "2026-08-04",
        "confidence": 0.99,
        "warnings": [],
    }
    gemini = FakeGeminiClient(json.dumps({"result": interpretation}))

    assistant = LocalFinancialAssistant(
        AssistantSettings(
            provider=LlmProvider.GEMINI, gemini_api_key="gemini-test-key"
        ),
        gemini_client=gemini,
    )
    response = await assistant.interpret_capture(
        "self transfer 25k ICICI -> HDFC", context
    )

    assert response is not None
    assert response.provider == "gemini"
    assert response.result.amount_paise == 2_500_000
    assert response.result.source_account_id == "icici-id"
    assert response.result.destination_account_id == "hdfc-id"
    body = gemini.aio.interactions.calls[0]
    assert body["store"] is False
    assert "25k means 25,000 rupees" in body["system_instruction"]
    normalized_prompt = " ".join(body["system_instruction"].casefold().split())
    assert "loans, lending, borrowing, and emis" in normalized_prompt
    assert "exact schema field identifiers" in normalized_prompt
    assert "freelance income, refunds, and interest" in normalized_prompt
    assert "named date such as 2 aug" in normalized_prompt
    assert "payment to a person" in normalized_prompt


@pytest.mark.asyncio
async def test_capture_diagnostics_classify_rate_limit_without_provider_text() -> None:
    context = CaptureContext(
        today="2026-08-04",
        timezone="Asia/Kolkata",
        accounts=[CaptureAccount(id="known-id", name="Known Bank", kind="bank")],
    )

    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            429,
            headers={"Retry-After": "7"},
            json={"error": "sensitive provider response must not escape"},
        )

    assistant = LocalFinancialAssistant(
        AssistantSettings(provider=LlmProvider.OLLAMA),
        transport=httpx.MockTransport(handler),
    )

    with pytest.raises(CaptureInterpretationError) as captured:
        await assistant.interpret_capture_or_raise("fictional capture", context)

    assert captured.value.kind is CaptureFailureKind.RATE_LIMITED
    assert captured.value.retryable is True
    assert captured.value.retry_after_seconds == 7.0
    assert str(captured.value) == "rate_limited"


@pytest.mark.asyncio
async def test_capture_interpretation_rejects_invented_account_id() -> None:
    context = CaptureContext(
        today="2026-08-04",
        timezone="Asia/Kolkata",
        accounts=[CaptureAccount(id="known-id", name="Known Bank", kind="bank")],
    )

    def handler(_request: httpx.Request) -> httpx.Response:
        interpretation = {
            "outcome": "draft",
            "kind": "expense",
            "amount_paise": 10_000,
            "description": "Coffee",
            "category_id": None,
            "category_name": None,
            "source_account_id": "invented-id",
            "destination_account_id": None,
            "member_ids": [],
            "split_equally": False,
            "occurred_on": None,
            "confidence": 0.9,
            "warnings": [],
        }
        return httpx.Response(
            200, json={"message": {"content": json.dumps(interpretation)}}
        )

    assistant = LocalFinancialAssistant(
        AssistantSettings(provider=LlmProvider.OLLAMA),
        transport=httpx.MockTransport(handler),
    )

    assert await assistant.interpret_capture("coffee 100", context) is None


@pytest.mark.asyncio
async def test_capture_interpretation_can_request_clarification_without_a_draft() -> None:
    context = CaptureContext(
        today="2026-08-04",
        timezone="Asia/Kolkata",
        accounts=[CaptureAccount(id="known-id", name="Known Bank", kind="bank")],
    )

    def handler(_request: httpx.Request) -> httpx.Response:
        result = {
            "outcome": "clarify",
            "question": "Which account should this use?",
            "missing": ["source_account_id"],
            "warnings": [],
        }
        return httpx.Response(200, json={"message": {"content": json.dumps(result)}})

    assistant = LocalFinancialAssistant(
        AssistantSettings(provider=LlmProvider.OLLAMA),
        transport=httpx.MockTransport(handler),
    )
    response = await assistant.interpret_capture("25k", context)

    assert response is not None
    assert response.result.outcome == "clarify"
    assert response.result.question == "Which account should this use?"


@pytest.mark.asyncio
async def test_gemini_failure_can_use_opt_in_ollama_fallback(
    financial_context: AssistantFinancialContext,
) -> None:
    requested_hosts: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requested_hosts.append(request.url.host or "")
        completion = {
            "message": ASSISTANT_INTENT_MESSAGES[AssistantIntent.SHARED],
            "intent": "shared",
            "widgets": [
                {
                    "type": "metric",
                    "title": "Shared balance",
                    "value_paise": 40000,
                    "caption": None,
                    "tone": "neutral",
                }
            ],
        }
        return httpx.Response(
            200,
            json={"message": {"content": json.dumps(completion)}},
        )

    assistant = LocalFinancialAssistant(
        AssistantSettings(
            provider=LlmProvider.GEMINI,
            gemini_api_key="test-key",
            ollama_fallback_enabled=True,
        ),
        transport=httpx.MockTransport(handler),
        gemini_client=FakeGeminiClient("invalid model response"),
    )
    response = await assistant.chat("What is the shared balance?", financial_context)

    assert requested_hosts == ["127.0.0.1"]
    assert response.mode == "model"
    assert response.provider == "ollama"
    assert response.model == "qwen3:4b-instruct"
    assert response.result.message == ASSISTANT_INTENT_MESSAGES[AssistantIntent.SHARED]


@pytest.mark.asyncio
async def test_invalid_model_payload_makes_assistant_unavailable(
    financial_context: AssistantFinancialContext,
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/chat"
        return httpx.Response(
            200,
            json={
                "message": {
                    "content": json.dumps(
                        {
                            "message": ASSISTANT_INTENT_MESSAGES[AssistantIntent.SPENDING],
                            "intent": "spending",
                            "widgets": [
                                {
                                    "type": "metric",
                                    "title": "Unsafe extra field",
                                    "value_paise": 1,
                                    "caption": None,
                                    "tone": "neutral",
                                    "sql": "delete from transactions",
                                }
                            ],
                        }
                    )
                }
            },
        )

    assistant = LocalFinancialAssistant(
        AssistantSettings(provider=LlmProvider.OLLAMA),
        transport=httpx.MockTransport(handler),
    )
    with pytest.raises(
        AssistantUnavailableError, match="AI assistant is unavailable"
    ):
        await assistant.chat("Show spending", financial_context)


@pytest.mark.asyncio
async def test_gemini_tag_suggestion_is_grounded_in_allowed_categories() -> None:
    suggestion = {
        "category_id": "food",
        "category_name": "Food",
        "confidence": 0.91,
        "reason": "The merchant is a restaurant.",
    }
    gemini = FakeGeminiClient(json.dumps(suggestion))

    assistant = LocalFinancialAssistant(
        AssistantSettings(
            provider=LlmProvider.GEMINI, gemini_api_key="gemini-test-key"
        ),
        gemini_client=gemini,
    )
    response = await assistant.suggest_tag(
        TagSuggestionRequest(
            description="Corner restaurant",
            amount_paise=85000,
            direction="expense",
            allowed_categories=[
                TagCategory(id="food", name="Food"),
                TagCategory(id="travel", name="Travel"),
            ],
        )
    )

    assert response.mode == "model"
    assert response.provider == "gemini"
    assert response.result.category_id == "food"
    body = gemini.aio.interactions.calls[0]
    assert body["response_format"]["mime_type"] == "application/json"
    assert "generic payment" in body["system_instruction"]


@pytest.mark.asyncio
async def test_invented_tag_makes_category_suggestion_unavailable() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/chat"
        suggestion = {
            "category_id": "invented",
            "category_name": "Crypto",
            "confidence": 1.0,
            "reason": "Invented by model.",
        }
        return httpx.Response(
            200,
            json={"message": {"content": json.dumps(suggestion)}},
        )

    assistant = LocalFinancialAssistant(
        AssistantSettings(provider=LlmProvider.OLLAMA),
        transport=httpx.MockTransport(handler),
    )
    with pytest.raises(
        AssistantUnavailableError, match="AI category suggestion is unavailable"
    ):
        await assistant.suggest_tag(
            TagSuggestionRequest(
                description="Unknown merchant",
                amount_paise=5000,
                direction="expense",
                allowed_categories=[TagCategory(id="food", name="Food")],
            )
        )


@pytest.mark.asyncio
async def test_disabled_assistant_endpoints_return_503_without_changing_ledger(
    client: httpx.AsyncClient,
    bootstrapped: dict[str, object],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    assert bootstrapped["created"] is True
    monkeypatch.setenv("ARTHA_LLM_PROVIDER", "disabled")
    before = (await client.get("/api/v1/transactions")).json()

    status_response = await client.get("/api/v1/assistant/status")
    chat_response = await client.post(
        "/api/v1/assistant/chat", json={"message": "Show my spending"}
    )
    tag_response = await client.post(
        "/api/v1/assistant/tag-suggestion",
        json={
            "description": "Food purchase",
            "amount_paise": 12000,
            "direction": "expense",
            "allowed_categories": [{"id": "food", "name": "Food"}],
        },
    )
    after = (await client.get("/api/v1/transactions")).json()

    assert status_response.status_code == 200
    assert status_response.json()["detail"] == "disabled"
    assert chat_response.status_code == 503
    assert chat_response.json() == {
        "detail": "AI is temporarily unavailable; the ledger was not changed."
    }
    assert tag_response.status_code == 503
    assert tag_response.json() == {
        "detail": (
            "AI category suggestion is temporarily unavailable; "
            "the ledger was not changed."
        )
    }
    assert before == after
