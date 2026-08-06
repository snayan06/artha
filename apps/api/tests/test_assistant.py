from __future__ import annotations

import json

import httpx
import pytest

from artha_api.assistant import (
    AssistantFinancialContext,
    AssistantSettings,
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
    TagCategory,
    TagSuggestionRequest,
)


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


@pytest.mark.asyncio
async def test_disabled_assistant_uses_deterministic_fallback(
    financial_context: AssistantFinancialContext,
) -> None:
    assistant = LocalFinancialAssistant(AssistantSettings(provider=LlmProvider.DISABLED))

    status = await assistant.status()
    response = await assistant.chat("How much did I spend?", financial_context)

    assert status.model_dump() == {
        "configured": False,
        "provider": "disabled",
        "model": None,
        "available": False,
        "active_provider": None,
        "ollama_fallback_enabled": False,
        "detail": "disabled",
    }
    assert response.mode == "deterministic_fallback"
    assert response.result.intent == "spending"
    assert response.result.widgets[0].type == "metric"


@pytest.mark.asyncio
async def test_groq_uses_strict_structured_output_without_tools_or_raw_rows(
    financial_context: AssistantFinancialContext,
) -> None:
    seen_request: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen_request["authorization"] = request.headers.get("Authorization")
        body = json.loads(request.content)
        seen_request["body"] = body
        completion = {
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
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": json.dumps(completion)}}]},
        )

    assistant = LocalFinancialAssistant(
        AssistantSettings(provider=LlmProvider.GROQ, groq_api_key="test-key"),
        transport=httpx.MockTransport(handler),
    )
    response = await assistant.chat("Show spending", financial_context)

    assert response.mode == "model"
    assert response.provider == "groq"
    assert seen_request["authorization"] == "Bearer test-key"
    body = seen_request["body"]
    assert isinstance(body, dict)
    assert "tools" not in body
    assert body["temperature"] == 0
    assert body["response_format"] == {"type": "json_object"}
    assert body["reasoning_effort"] == "none"
    prompt = body["messages"][1]["content"]
    assert "account_id" not in prompt
    assert "description" not in prompt
    assert "notes" not in prompt


@pytest.mark.asyncio
async def test_groq_capture_interpretation_resolves_25k_transfer_to_allowed_accounts() -> None:
    context = CaptureContext(
        today="2026-08-04",
        timezone="Asia/Kolkata",
        accounts=[
            CaptureAccount(id="icici-id", name="ICICI Bank", kind="bank"),
            CaptureAccount(id="hdfc-id", name="HDFC Bank", kind="bank"),
        ],
        categories=[CaptureCategory(id="other-id", name="Other", kind="both")],
    )

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        assert "25k means 25,000 rupees" in body["messages"][0]["content"]
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
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": json.dumps(interpretation)}}]},
        )

    assistant = LocalFinancialAssistant(
        AssistantSettings(provider=LlmProvider.GROQ, groq_api_key="test-key"),
        transport=httpx.MockTransport(handler),
    )
    response = await assistant.interpret_capture(
        "self transfer 25k ICICI -> HDFC", context
    )

    assert response is not None
    assert response.mode == "model"
    assert response.result.amount_paise == 2_500_000
    assert response.result.source_account_id == "icici-id"
    assert response.result.destination_account_id == "hdfc-id"


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
        AssistantSettings(provider=LlmProvider.GROQ, groq_api_key="test-key"),
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
            200,
            json={"choices": [{"message": {"content": json.dumps(interpretation)}}]},
        )

    assistant = LocalFinancialAssistant(
        AssistantSettings(provider=LlmProvider.GROQ, groq_api_key="test-key"),
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
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": json.dumps(result)}}]},
        )

    assistant = LocalFinancialAssistant(
        AssistantSettings(provider=LlmProvider.GROQ, groq_api_key="test-key"),
        transport=httpx.MockTransport(handler),
    )
    response = await assistant.interpret_capture("25k", context)

    assert response is not None
    assert response.result.outcome == "clarify"
    assert response.result.question == "Which account should this use?"


@pytest.mark.asyncio
async def test_groq_failure_can_use_opt_in_ollama_fallback(
    financial_context: AssistantFinancialContext,
) -> None:
    requested_hosts: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requested_hosts.append(request.url.host or "")
        if request.url.host == "api.groq.com":
            return httpx.Response(503, json={"error": "unavailable"})
        completion = {
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
            provider=LlmProvider.GROQ,
            groq_api_key="test-key",
            ollama_fallback_enabled=True,
        ),
        transport=httpx.MockTransport(handler),
    )
    response = await assistant.chat("What is the shared balance?", financial_context)

    assert requested_hosts == ["api.groq.com", "127.0.0.1"]
    assert response.mode == "model"
    assert response.provider == "ollama"
    assert response.model == "qwen3:4b-instruct"


@pytest.mark.asyncio
async def test_invalid_model_payload_falls_back_deterministically(
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
    response = await assistant.chat("Show spending", financial_context)

    assert response.mode == "deterministic_fallback"
    assert response.result.intent == "spending"


@pytest.mark.asyncio
async def test_status_never_serializes_groq_key() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/openai/v1/models"
        return httpx.Response(200, json={"data": []})

    assistant = LocalFinancialAssistant(
        AssistantSettings(provider=LlmProvider.GROQ, groq_api_key="never-return-me"),
        transport=httpx.MockTransport(handler),
    )
    status = await assistant.status()

    serialized = status.model_dump_json()
    assert status.available is True
    assert status.active_provider == "groq"
    assert "never-return-me" not in serialized


@pytest.mark.asyncio
async def test_tag_suggestion_is_grounded_in_allowed_categories() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        prompt = json.loads(
            body["messages"][1]["content"].split("\nRequired response JSON schema:\n")[0]
        )
        assert set(prompt) == {
            "description",
            "amount_paise",
            "direction",
            "allowed_categories",
        }
        suggestion = {
            "category_id": "food",
            "category_name": "Food",
            "confidence": 0.91,
            "reason": "The merchant is a restaurant.",
        }
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": json.dumps(suggestion)}}]},
        )

    assistant = LocalFinancialAssistant(
        AssistantSettings(provider=LlmProvider.GROQ, groq_api_key="test-key"),
        transport=httpx.MockTransport(handler),
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
    assert response.result.category_id == "food"
    assert response.result.confidence == 0.91


@pytest.mark.asyncio
async def test_invented_tag_is_rejected_and_gracefully_falls_back() -> None:
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
    response = await assistant.suggest_tag(
        TagSuggestionRequest(
            description="Unknown merchant",
            amount_paise=5000,
            direction="expense",
            allowed_categories=[TagCategory(id="food", name="Food")],
        )
    )

    assert response.mode == "deterministic_fallback"
    assert response.result.category_id is None
    assert response.result.confidence == 0


@pytest.mark.asyncio
async def test_assistant_endpoints_are_read_only_when_provider_is_disabled(
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
    assert chat_response.status_code == 200
    assert chat_response.json()["mode"] == "deterministic_fallback"
    assert tag_response.status_code == 200
    assert tag_response.json()["result"]["category_id"] == "food"
    assert before == after
