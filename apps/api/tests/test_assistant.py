from __future__ import annotations

import json

import httpx
import pytest

from artha_api.assistant import (
    AssistantFinancialContext,
    AssistantSettings,
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
