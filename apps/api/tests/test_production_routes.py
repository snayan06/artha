from __future__ import annotations

from datetime import datetime
from typing import Any, cast
from uuid import UUID

import pytest
from fastapi import FastAPI, HTTPException
from httpx import ASGITransport, AsyncClient
from pydantic import ValidationError

from artha_api import production_routes
from artha_api.assistant import (
    AssistantChatRequest,
    AssistantStatus,
    CaptureClarification,
    CaptureDraftInterpretation,
    CaptureInterpretationResponse,
    LlmProvider,
    LocalFinancialAssistant,
    TagSuggestion,
    TagSuggestionRequest,
    TagSuggestionResponse,
)
from artha_api.auth import AuthContext, get_auth_context
from artha_api.production_routes import (
    ProductionDraft,
    ProductionSplit,
    ProductionTagSuggestionRequest,
    assistant_chat,
    assistant_status,
    assistant_tag_suggestion,
    confirm_transaction,
    list_transactions,
    member_balances,
    parse_draft,
    profile,
)
from artha_api.schemas import ParseRequest
from artha_api.supabase_rest import SupabaseRestClient
from artha_api.transaction_metadata import (
    ModelAttribute,
    ModelFieldEvidence,
    ModelTag,
    ReviewedAttribute,
    ReviewedEvidence,
    ReviewedMetadata,
    SuggestedTag,
)

HOUSEHOLD_ID = "00000000-0000-0000-0000-000000000100"
OWNER_ID = "00000000-0000-0000-0000-000000000101"
MEMBER_ID = "00000000-0000-0000-0000-000000000102"
ACCOUNT_ID = "00000000-0000-0000-0000-000000000103"
DESTINATION_ACCOUNT_ID = "00000000-0000-0000-0000-000000000107"
CATEGORY_ID = "00000000-0000-0000-0000-000000000104"
USER_ID = "00000000-0000-0000-0000-000000000105"
TRANSACTION_ID = "00000000-0000-0000-0000-000000000106"


@pytest.fixture(autouse=True)
def approve_private_ai_by_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ARTHA_AI_DATA_POLICY", "private_approved")
    monkeypatch.delenv("ARTHA_DEMO_ACCOUNT_USER_ID", raising=False)


class FakeCaptureContextClient:
    def __init__(
        self,
        *,
        accounts: list[dict[str, Any]],
        categories: list[dict[str, Any]],
        include_owner: bool = True,
    ) -> None:
        self.accounts = accounts
        self.categories = categories
        self.include_owner = include_owner
        self.params_by_path: dict[str, dict[str, str]] = {}

    async def rpc(self, name: str, payload: dict[str, Any] | None = None) -> Any:
        if name == "get_current_household":
            assert payload is None
            return HOUSEHOLD_ID
        if name == "get_account_balances":
            assert payload == {"p_household_id": HOUSEHOLD_ID}
            return []
        raise AssertionError(f"unexpected RPC: {name}")

    async def request(self, method: str, path: str, **kwargs: Any) -> Any:
        assert method == "GET"
        self.params_by_path[path] = kwargs["params"]
        if path == "household_members":
            return [
                {
                    "id": OWNER_ID,
                    "profile_id": USER_ID if self.include_owner else "another-user",
                    "display_name": "Owner",
                    "member_type": "user",
                    "role": "owner",
                    "is_active": True,
                    "created_at": "2026-08-04T00:00:00+00:00",
                }
            ]
        if path == "accounts":
            return self.accounts
        if path == "categories":
            return self.categories
        raise AssertionError(f"unexpected path: {path}")


async def test_production_capture_context_is_household_scoped_and_grounded() -> None:
    client = FakeCaptureContextClient(
        accounts=[
            {
                "id": ACCOUNT_ID,
                "name": "Known Bank",
                "account_type": "bank",
                "currency": "INR",
                "opening_balance_paise": 50_000,
                "credit_limit_paise": None,
                "statement_day": None,
                "payment_due_day": None,
                "is_archived": False,
                "created_at": "2026-08-04T00:00:00+00:00",
            }
        ],
        categories=[
            {"id": "expense", "name": "Food", "category_type": "expense"},
            {"id": "income", "name": "Salary", "category_type": "income"},
            {"id": "both", "name": "Other", "category_type": "both"},
            {"id": "invalid", "name": "Invalid", "category_type": "transfer"},
        ],
    )

    response = await production_routes.capture_context(
        cast(SupabaseRestClient, client),
        AuthContext(user_id=USER_ID),
    )

    assert response.model_dump(mode="json") == {
        "accounts": [{"id": ACCOUNT_ID, "name": "Known Bank", "kind": "bank"}],
        "categories": [
            {"id": "expense", "name": "Food", "kind": "expense"},
            {"id": "both", "name": "Other", "kind": "both"},
            {"id": "income", "name": "Salary", "kind": "income"},
        ],
    }
    assert client.params_by_path["accounts"] == expect_capture_scope(
        "id,name,account_type,currency,opening_balance_paise,credit_limit_paise,"
        "statement_day,payment_due_day,is_archived,created_at",
        order="created_at.asc,id.asc",
    )
    assert client.params_by_path["categories"] == expect_capture_scope(
        "id,name,category_type,is_archived", order="name.asc,id.asc"
    )


async def test_production_capture_context_rejects_a_non_owner() -> None:
    client = FakeCaptureContextClient(accounts=[], categories=[], include_owner=False)

    with pytest.raises(HTTPException) as error:
        await production_routes.capture_context(
            cast(SupabaseRestClient, client),
            AuthContext(user_id=USER_ID),
        )

    assert error.value.status_code == 403


async def test_production_capture_context_returns_empty_lists() -> None:
    response = await production_routes.capture_context(
        cast(
            SupabaseRestClient,
            FakeCaptureContextClient(accounts=[], categories=[]),
        ),
        AuthContext(user_id=USER_ID),
    )

    assert response.model_dump(mode="json") == {"accounts": [], "categories": []}


def expect_capture_scope(select: str, *, order: str | None = None) -> dict[str, str]:
    params = {
        "household_id": f"eq.{HOUSEHOLD_ID}",
        "is_archived": "eq.false",
        "select": select,
    }
    if order is not None:
        params["order"] = order
    return params


class FakeAccountManagementClient(FakeCaptureContextClient):
    def __init__(self) -> None:
        super().__init__(
            accounts=[
                {
                    "id": ACCOUNT_ID,
                    "name": "Known Bank",
                    "account_type": "bank",
                    "currency": "INR",
                    "opening_balance_paise": 50_000,
                    "credit_limit_paise": None,
                    "statement_day": None,
                    "payment_due_day": None,
                    "is_archived": False,
                    "created_at": "2026-08-04T00:00:00+00:00",
                }
            ],
            categories=[],
        )
        self.rpc_calls: list[tuple[str, dict[str, Any] | None]] = []

    async def rpc(self, name: str, payload: dict[str, Any] | None = None) -> Any:
        if name in {"get_current_household", "get_account_balances"}:
            return await super().rpc(name, payload)
        self.rpc_calls.append((name, payload))
        return {"id": TRANSACTION_ID}


async def test_managed_account_listing_can_include_archived_rows() -> None:
    client = FakeAccountManagementClient()

    rows = await production_routes.list_accounts(
        cast(SupabaseRestClient, client),
        AuthContext(user_id=USER_ID),
        include_archived=True,
    )

    assert rows[0]["current_balance_paise"] == 50_000
    assert "is_archived" not in client.params_by_path["accounts"]


async def test_balance_reconciliation_calls_owner_only_adjustment_rpc() -> None:
    client = FakeAccountManagementClient()
    payload_type = production_routes.AccountBalanceAdjustmentRequest

    result = await production_routes.reconcile_account_balance(
        account_id=ACCOUNT_ID,
        payload=payload_type(
            actual_balance_paise=75_000,
            reason="Bank statement reconciliation",
            occurred_at="2026-08-09T12:00:00+00:00",
        ),
        idempotency_key="account-adjustment-0001",
        client=cast(SupabaseRestClient, client),
        auth=AuthContext(user_id=USER_ID),
    )

    assert result["current_balance_paise"] == 50_000
    assert client.rpc_calls[0][0] == "create_balance_adjustment"


async def test_production_assistant_routes_return_503_when_provider_is_disabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ARTHA_LLM_PROVIDER", "disabled")
    auth = AuthContext(user_id=USER_ID)

    async def empty_dashboard(_client: object, _auth: AuthContext) -> dict[str, object]:
        return {
            "total_balance_paise": 0,
            "spend_paise": 0,
            "income_paise": 0,
            "member_balances": [],
            "spend_by_category": [],
            "monthly": [],
            "recent_transactions": [],
        }

    monkeypatch.setattr("artha_api.production_routes.dashboard", empty_dashboard)

    with pytest.raises(HTTPException) as chat_error:
        await assistant_chat(
            AssistantChatRequest(message="Show my spending"),
            cast(SupabaseRestClient, FakeProductionClient()),
            auth,
        )
    with pytest.raises(HTTPException) as tag_error:
        await assistant_tag_suggestion(
            ProductionTagSuggestionRequest(
                description="Food purchase",
                amount_paise=12_000,
                direction="expense",
            ),
            cast(SupabaseRestClient, FakeProductionClient()),
            auth,
        )

    assert chat_error.value.status_code == 503
    assert chat_error.value.detail == (
        "AI is temporarily unavailable; the ledger was not changed."
    )
    assert tag_error.value.status_code == 503
    assert tag_error.value.detail == (
        "AI category suggestion is temporarily unavailable; "
        "the ledger was not changed."
    )


class FakeProductionClient:
    def __init__(
        self,
        *,
        categories: list[dict[str, Any]] | None = None,
        accounts: list[dict[str, Any]] | None = None,
        merchant_rules: list[dict[str, Any]] | None = None,
    ) -> None:
        self.confirm_payload: dict[str, Any] | None = None
        self.transfer_payload: dict[str, Any] | None = None
        self.correction_payload: dict[str, Any] | None = None
        self.void_payload: dict[str, Any] | None = None
        self.settlement_payload: dict[str, Any] | None = None
        self.activity_payload: dict[str, Any] | None = None
        self.rpc_names: list[str] = []
        self.categories = (
            categories
            if categories is not None
            else [
                {
                    "id": CATEGORY_ID,
                    "name": "Groceries",
                    "category_type": "expense",
                    "is_archived": False,
                }
            ]
        )
        self.accounts = accounts
        self.merchant_rules = merchant_rules or []

    async def rpc(self, name: str, payload: dict[str, Any] | None = None) -> Any:
        self.rpc_names.append(name)
        if name == "get_current_household":
            return HOUSEHOLD_ID
        if name == "confirm_transaction":
            self.confirm_payload = payload
            return {
                "id": TRANSACTION_ID,
                "account_id": ACCOUNT_ID,
                "category_id": CATEGORY_ID,
                "paid_by_member_id": OWNER_ID,
                "direction": "expense",
                "amount_paise": 10_000,
                "occurred_at": "2026-08-04T12:00:00+00:00",
                "merchant": "Groceries",
                "note": None,
                "created_at": "2026-08-04T12:00:00+00:00",
            }
        if name == "create_transfer":
            self.transfer_payload = payload
            return [{
                "transfer_link_id": TRANSACTION_ID,
                "transfer_out_transaction_id": "00000000-0000-0000-0000-000000000108",
                "transfer_in_transaction_id": "00000000-0000-0000-0000-000000000109",
            }]
        if name == "replace_transaction":
            self.correction_payload = payload
            return {
                "original_transaction_id": TRANSACTION_ID,
                "replacement_transaction_id": TRANSACTION_ID,
                "replacement_row_id": "00000000-0000-0000-0000-000000000108",
                "corrected_at": "2026-08-10T12:00:00+00:00",
            }
        if name == "void_ledger_activity":
            self.void_payload = payload
            return {"id": TRANSACTION_ID, "deleted": True, "status": "voided"}
        if name == "settle_member_balance":
            self.settlement_payload = payload
            return {
                "id": "00000000-0000-0000-0000-000000000110",
                "member_id": MEMBER_ID,
                "amount_paise": 2_500,
                "balance_paise": 1_500,
            }
        if name == "get_account_balances":
            return [{"account_id": ACCOUNT_ID, "balance_paise": 50_000}]
        if name == "get_member_balances":
            return [{"member_id": MEMBER_ID, "balance_paise": 4_000}]
        if name == "list_ledger_activity":
            self.activity_payload = payload
            return [{
                "id": TRANSACTION_ID,
                "kind": "transfer",
                "amount_paise": 2_500_000,
                "personal_share_paise": 2_500_000,
                "description": "Self transfer",
                "category": "Transfer",
                "paid_by_member_id": None,
                "source_account_id": ACCOUNT_ID,
                "destination_account_id": DESTINATION_ACCOUNT_ID,
                "settlement_member_id": None,
                "settlement_direction": None,
                "occurred_at": "2026-08-04T12:00:00+00:00",
                "notes": "Self transfer",
                "splits": [],
                "is_deleted": False,
                "created_at": "2026-08-04T12:00:00+00:00",
                "updated_at": "2026-08-04T12:00:00+00:00",
                "account_delta_paise": 0,
                "member_balance_deltas": [],
            }]
        if name == "list_ledger_activity_page":
            self.activity_payload = payload
            first = {
                "id": TRANSACTION_ID,
                "kind": "transfer",
                "amount_paise": 2_500_000,
                "personal_share_paise": 2_500_000,
                "description": "Self transfer",
                "category": "Transfer",
                "paid_by_member_id": None,
                "source_account_id": ACCOUNT_ID,
                "destination_account_id": DESTINATION_ACCOUNT_ID,
                "settlement_member_id": None,
                "settlement_direction": None,
                "occurred_at": "2026-08-04T12:00:00+00:00",
                "notes": "Self transfer",
                "splits": [],
                "is_deleted": False,
                "created_at": "2026-08-04T12:00:00+00:00",
                "updated_at": "2026-08-04T12:00:00+00:00",
                "account_delta_paise": 0,
                "member_balance_deltas": [],
            }
            older = {
                **first,
                "id": "00000000-0000-0000-0000-000000000111",
                "occurred_at": "2026-08-03T12:00:00+00:00",
                "created_at": "2026-08-03T12:00:00+00:00",
            }
            return [first, older] if payload and payload["p_before_id"] is None else [older]
        if name == "search_ledger_activity":
            self.activity_payload = payload
            return [{
                "id": TRANSACTION_ID,
                "kind": "expense",
                "description": "Late night Zomato",
                "notes": "Team dinner",
            }]
        raise AssertionError(f"unexpected RPC: {name}")

    async def request(self, _method: str, path: str, **_kwargs: Any) -> Any:
        if path == "household_members":
            return [
                {
                    "id": OWNER_ID,
                    "profile_id": USER_ID,
                    "display_name": "Owner",
                    "member_type": "user",
                    "role": "owner",
                    "is_active": True,
                    "created_at": "2026-08-04T00:00:00+00:00",
                },
                {
                    "id": MEMBER_ID,
                    "profile_id": None,
                    "display_name": "Family member",
                    "member_type": "participant",
                    "role": "member",
                    "is_active": True,
                    "created_at": "2026-08-04T00:00:01+00:00",
                },
            ]
        if path == "categories":
            return self.categories
        if path == "accounts":
            return self.accounts if self.accounts is not None else [{
                "id": ACCOUNT_ID,
                "name": "Known Bank",
                "account_type": "bank",
                "currency": "INR",
                "opening_balance_paise": 50_000,
                "credit_limit_paise": None,
                "statement_day": None,
                "payment_due_day": None,
                "is_archived": False,
                "created_at": "2026-08-04T00:00:00+00:00",
            }]
        if path == "merchant_rules":
            return self.merchant_rules
        if path == "households":
            return [{"id": HOUSEHOLD_ID, "name": "Test household"}]
        raise AssertionError(f"unexpected path: {path}")


class FakeTagSuggestionClient:
    def __init__(
        self,
        categories: list[dict[str, str]],
        *,
        household_id: str | None = HOUSEHOLD_ID,
    ) -> None:
        self.categories = categories
        self.household_id = household_id
        self.category_params: dict[str, str] | None = None

    async def rpc(self, name: str, payload: dict[str, Any] | None = None) -> Any:
        assert name == "get_current_household"
        assert payload is None
        return self.household_id

    async def request(self, method: str, path: str, **kwargs: Any) -> Any:
        assert method == "GET"
        assert path == "categories"
        self.category_params = kwargs["params"]
        return self.categories


def test_production_tag_suggestion_rejects_caller_owned_category_allow_list() -> None:
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        ProductionTagSuggestionRequest.model_validate(
            {
                "description": "Food purchase",
                "amount_paise": 12_000,
                "direction": "expense",
                "allowed_categories": [{"id": "invented", "name": "Invented"}],
            }
        )


@pytest.mark.parametrize(
    ("direction", "expected_ids"),
    [
        ("expense", ["expense-category", "both-category"]),
        ("income", ["income-category", "both-category"]),
    ],
)
async def test_production_tag_suggestion_uses_only_eligible_household_categories(
    monkeypatch: pytest.MonkeyPatch,
    direction: str,
    expected_ids: list[str],
) -> None:
    client = FakeTagSuggestionClient(
        [
            {"id": "expense-category", "name": "Food", "category_type": "expense"},
            {"id": "income-category", "name": "Salary", "category_type": "income"},
            {"id": "both-category", "name": "Other", "category_type": "both"},
        ]
    )
    captured: list[Any] = []

    class CapturingAssistant:
        async def suggest_tag(self, payload: Any) -> TagSuggestionResponse:
            captured.append(payload)
            category = payload.allowed_categories[0]
            return TagSuggestionResponse(
                provider=LlmProvider.GEMINI,
                model="test-model",
                mode="model",
                result=TagSuggestion(
                    category_id=category.id,
                    category_name=category.name,
                    confidence=0.9,
                    reason="Grounded in the household category list.",
                ),
            )

    monkeypatch.setattr(
        "artha_api.production_routes.LocalFinancialAssistant", CapturingAssistant
    )

    await assistant_tag_suggestion(
        ProductionTagSuggestionRequest(
            description="  Food   purchase  ",
            amount_paise=12_000,
            direction=direction,
        ),
        cast(SupabaseRestClient, client),
        AuthContext(user_id=USER_ID),
    )

    assert client.category_params == {
        "household_id": f"eq.{HOUSEHOLD_ID}",
        "is_archived": "eq.false",
        "select": "id,name,category_type,is_archived",
        "order": "name.asc,id.asc",
    }
    assert len(captured) == 1
    assert isinstance(captured[0], TagSuggestionRequest)
    assert captured[0].description == "Food purchase"
    assert [category.id for category in captured[0].allowed_categories] == expected_ids


async def test_production_tag_suggestion_passes_more_than_fifty_categories(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = FakeTagSuggestionClient(
        [
            {
                "id": f"category-{index}",
                "name": f"Category {index}",
                "category_type": "expense",
            }
            for index in range(51)
        ]
    )
    captured: list[TagSuggestionRequest] = []

    class CapturingAssistant:
        async def suggest_tag(
            self, payload: TagSuggestionRequest
        ) -> TagSuggestionResponse:
            captured.append(payload)
            category = payload.allowed_categories[-1]
            return TagSuggestionResponse(
                provider=LlmProvider.GEMINI,
                model="test-model",
                mode="model",
                result=TagSuggestion(
                    category_id=category.id,
                    category_name=category.name,
                    confidence=0.9,
                    reason="Grounded in the complete household category list.",
                ),
            )

    monkeypatch.setattr(
        "artha_api.production_routes.LocalFinancialAssistant", CapturingAssistant
    )

    result = await assistant_tag_suggestion(
        ProductionTagSuggestionRequest(
            description="Household transaction",
            amount_paise=12_000,
            direction="expense",
        ),
        cast(SupabaseRestClient, client),
        AuthContext(user_id=USER_ID),
    )

    assert len(captured) == 1
    assert len(captured[0].allowed_categories) == 51
    assert result.result.category_id == "category-50"


async def test_production_tag_suggestion_rejects_when_no_category_is_eligible(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = FakeTagSuggestionClient(
        [{"id": "income-category", "name": "Salary", "category_type": "income"}]
    )

    def unexpected_assistant() -> None:
        raise AssertionError("model must not be called without an eligible category")

    monkeypatch.setattr(
        "artha_api.production_routes.LocalFinancialAssistant", unexpected_assistant
    )

    with pytest.raises(HTTPException) as error:
        await assistant_tag_suggestion(
            ProductionTagSuggestionRequest(
                description="Food purchase",
                amount_paise=12_000,
                direction="expense",
            ),
            cast(SupabaseRestClient, client),
            AuthContext(user_id=USER_ID),
        )

    assert error.value.status_code == 422


async def test_production_tag_suggestion_requires_an_authenticated_household(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = FakeTagSuggestionClient([], household_id=None)

    def unexpected_assistant() -> None:
        raise AssertionError("model must not be called without a household")

    monkeypatch.setattr(
        "artha_api.production_routes.LocalFinancialAssistant", unexpected_assistant
    )

    with pytest.raises(HTTPException) as error:
        await assistant_tag_suggestion(
            ProductionTagSuggestionRequest(
                description="Food purchase",
                amount_paise=12_000,
                direction="expense",
            ),
            cast(SupabaseRestClient, client),
            AuthContext(user_id=USER_ID),
        )

    assert error.value.status_code == 409


async def test_production_confirmation_adds_owner_share_to_atomic_rpc() -> None:
    fake = FakeProductionClient()
    draft = ProductionDraft(
        kind="expense",
        amount_paise=10_000,
        description="Groceries",
        category="Groceries",
        personal_share_paise=6_000,
        splits=[ProductionSplit(member_id=MEMBER_ID, amount_paise=4_000)],
        source_account_id=ACCOUNT_ID,
    )

    result = await confirm_transaction(
        draft,
        cast(SupabaseRestClient, fake),
        AuthContext(user_id=USER_ID),
        "test-idempotency-key",
    )

    assert fake.confirm_payload is not None
    assert fake.confirm_payload["p_splits"] == [
        {"member_id": MEMBER_ID, "amount_paise": 4_000},
        {"member_id": OWNER_ID, "amount_paise": 6_000},
    ]
    assert result["personal_share_paise"] == 6_000
    assert result["splits"] == [{"member_id": MEMBER_ID, "amount_paise": 4_000}]


async def test_production_confirmation_persists_only_reviewed_metadata() -> None:
    fake = FakeProductionClient(
        categories=[
            {
                "id": CATEGORY_ID,
                "name": "Food & Dining",
                "category_type": "expense",
                "is_archived": False,
            }
        ]
    )
    draft = ProductionDraft(
        kind="expense",
        amount_paise=68_000,
        description="Burger King",
        category="Food & Dining",
        platform="Zomato",
        subcategory="Fast Food",
        metadata=ReviewedMetadata(
            evidence={
                "merchant": ReviewedEvidence(
                    source="user_corrected", confidence=0.99, review_status="reviewed"
                ),
                "platform": ReviewedEvidence(
                    source="user_corrected", confidence=0.99, review_status="reviewed"
                ),
                "category": ReviewedEvidence(
                    source="user_corrected", confidence=1, review_status="reviewed"
                ),
            },
            attributes=[
                ReviewedAttribute(
                    key="order_channel",
                    value="Delivery",
                    source="user_corrected",
                    confidence=1,
                    review_status="reviewed",
                )
            ],
        ),
        tags=[
            SuggestedTag(
                name="Date Night",
                normalized_name="date night",
                source="user_corrected",
                confidence=0.98,
                review_status="reviewed",
            )
        ],
        personal_share_paise=68_000,
        source_account_id=ACCOUNT_ID,
    )

    await confirm_transaction(
        draft,
        cast(SupabaseRestClient, fake),
        AuthContext(user_id=USER_ID),
        "reviewed-metadata",
    )

    assert fake.confirm_payload is not None
    assert fake.confirm_payload["p_metadata"] == {
        "source": "artha-api",
        "version": 1,
        "platform": "Zomato",
        "subcategory": "Fast Food",
        "evidence": {
            "merchant": {
                "source": "user_corrected",
                "confidence": 0.99,
                "review_status": "reviewed",
            },
            "platform": {
                "source": "user_corrected",
                "confidence": 0.99,
                "review_status": "reviewed",
            },
            "category": {
                "source": "user_corrected",
                "confidence": 1.0,
                "review_status": "reviewed",
            },
        },
        "attributes": [
            {
                "key": "order_channel",
                "value": "Delivery",
                "source": "user_corrected",
                "confidence": 1.0,
                "review_status": "reviewed",
            }
        ],
        "tags": [
            {
                "name": "Date Night",
                "normalized_name": "date night",
                "source": "user_corrected",
                "confidence": 0.98,
                "review_status": "reviewed",
            }
        ],
    }


def test_production_confirmation_rejects_unreviewed_or_transfer_metadata() -> None:
    with pytest.raises(ValidationError, match="reviewed before confirmation"):
        ProductionDraft(
            kind="expense",
            amount_paise=10_000,
            description="Dinner",
            category="Food & Dining",
            metadata=ReviewedMetadata(
                evidence={
                    "merchant": ReviewedEvidence(
                        source="model_suggested",
                        confidence=0.8,
                        review_status="needs_review",
                    )
                }
            ),
            personal_share_paise=10_000,
            source_account_id=ACCOUNT_ID,
        )


def test_production_confirmation_rejects_untrusted_or_redundant_metadata() -> None:
    with pytest.raises(ValidationError, match="reviewed metadata provenance"):
        ProductionDraft(
            kind="expense",
            amount_paise=10_000,
            description="Dinner",
            category="Food & Dining",
            metadata=ReviewedMetadata(
                evidence={
                    "category": ReviewedEvidence(
                        source="safe_catalog",
                        confidence=1,
                        review_status="reviewed",
                    )
                }
            ),
            personal_share_paise=10_000,
            source_account_id=ACCOUNT_ID,
        )

    with pytest.raises(ValidationError, match="tag duplicates a transaction field"):
        ProductionDraft(
            kind="expense",
            amount_paise=10_000,
            description="Date Night",
            category="Food & Dining",
            metadata=ReviewedMetadata(),
            tags=[
                SuggestedTag(
                    name="Date Night",
                    normalized_name="date night",
                    source="user_corrected",
                    confidence=1,
                    review_status="reviewed",
                )
            ],
            personal_share_paise=10_000,
            source_account_id=ACCOUNT_ID,
        )

    with pytest.raises(ValidationError, match="platform cannot be blank"):
        ProductionDraft(
            kind="expense",
            amount_paise=10_000,
            description="Dinner",
            category="Food & Dining",
            platform="   ",
            personal_share_paise=10_000,
            source_account_id=ACCOUNT_ID,
        )

    with pytest.raises(ValidationError, match="structured fields require metadata"):
        ProductionDraft(
            kind="expense",
            amount_paise=10_000,
            description="Dinner",
            category="Food & Dining",
            platform="Zomato",
            personal_share_paise=10_000,
            source_account_id=ACCOUNT_ID,
        )

    with pytest.raises(ValidationError, match="transfer cannot contain metadata"):
        ProductionDraft(
            kind="transfer",
            amount_paise=10_000,
            description="Self transfer",
            category="Transfer",
            platform="Zomato",
            personal_share_paise=10_000,
            source_account_id=ACCOUNT_ID,
            destination_account_id=DESTINATION_ACCOUNT_ID,
        )


@pytest.mark.parametrize(
    ("category", "rows"),
    [
        (
            "Invented",
            [
                {
                    "id": CATEGORY_ID,
                    "name": "Groceries",
                    "category_type": "expense",
                    "is_archived": False,
                }
            ],
        ),
        (
            "Gro%",
            [
                {
                    "id": CATEGORY_ID,
                    "name": "Groceries",
                    "category_type": "expense",
                    "is_archived": False,
                }
            ],
        ),
        (
            "Groceries",
            [
                {
                    "id": CATEGORY_ID,
                    "name": "Groceries",
                    "category_type": "expense",
                    "is_archived": True,
                }
            ],
        ),
        (
            "Salary",
            [
                {
                    "id": CATEGORY_ID,
                    "name": "Salary",
                    "category_type": "income",
                    "is_archived": False,
                }
            ],
        ),
    ],
    ids=["invented", "wildcard", "archived", "wrong-direction"],
)
async def test_production_confirmation_rejects_ungrounded_categories(
    category: str,
    rows: list[dict[str, Any]],
) -> None:
    fake = FakeProductionClient(categories=rows)
    draft = ProductionDraft(
        kind="expense",
        amount_paise=10_000,
        description="Crafted category",
        category=category,
        personal_share_paise=10_000,
        source_account_id=ACCOUNT_ID,
    )

    with pytest.raises(HTTPException) as error:
        await confirm_transaction(
            draft,
            cast(SupabaseRestClient, fake),
            AuthContext(user_id=USER_ID),
            f"category-{category}",
        )

    assert error.value.status_code == 422
    assert fake.confirm_payload is None


async def test_production_confirmation_accepts_exact_normalized_category() -> None:
    fake = FakeProductionClient()
    draft = ProductionDraft(
        kind="expense",
        amount_paise=10_000,
        description="Grounded category",
        category="  gRoCeRiEs  ",
        personal_share_paise=10_000,
        source_account_id=ACCOUNT_ID,
    )

    await confirm_transaction(
        draft,
        cast(SupabaseRestClient, fake),
        AuthContext(user_id=USER_ID),
        "category-normalized",
    )

    assert fake.confirm_payload is not None
    assert fake.confirm_payload["p_category_id"] == CATEGORY_ID


async def test_production_confirmation_rejects_blank_descriptions_before_any_rpc() -> None:
    fake = FakeProductionClient()
    app = FastAPI()
    app.include_router(production_routes.router)
    app.dependency_overrides[get_auth_context] = lambda: AuthContext(user_id=USER_ID)
    app.dependency_overrides[production_routes.production_client] = lambda: fake
    cases = [
        {"kind": "expense", "category": "Groceries"},
        {"kind": "income", "category": "Salary"},
        {
            "kind": "transfer",
            "category": "Crafted transfer category",
            "destination_account_id": DESTINATION_ACCOUNT_ID,
        },
    ]

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        for index, fields in enumerate(cases):
            response = await client.post(
                "/api/v1/transactions/confirm",
                headers={"Idempotency-Key": f"blank-description-{index}"},
                json={
                    **fields,
                    "amount_paise": 10_000,
                    "description": " \n  ",
                    "personal_share_paise": 10_000,
                    "splits": [],
                    "source_account_id": ACCOUNT_ID,
                },
            )
            assert response.status_code == 422

    assert fake.rpc_names == []
    assert fake.confirm_payload is None
    assert fake.transfer_payload is None


async def test_production_confirmation_trims_a_valid_description() -> None:
    fake = FakeProductionClient()
    draft = ProductionDraft(
        kind="expense",
        amount_paise=10_000,
        description="  Family groceries  ",
        category="Groceries",
        personal_share_paise=10_000,
        source_account_id=ACCOUNT_ID,
    )

    assert draft.description == "Family groceries"
    await confirm_transaction(
        draft,
        cast(SupabaseRestClient, fake),
        AuthContext(user_id=USER_ID),
        "trimmed-description",
    )
    assert fake.confirm_payload is not None
    assert fake.confirm_payload["p_merchant"] == "Family groceries"


async def test_profile_hydrates_server_owned_household_and_participants() -> None:
    fake = FakeProductionClient()

    result = await profile(
        cast(SupabaseRestClient, fake),
        AuthContext(user_id=USER_ID),
    )

    assert result == {
        "display_name": "Owner",
        "household_name": "Test household",
        "is_demo": False,
        "members": [
            {
                "id": MEMBER_ID,
                "name": "Family member",
                "is_archived": False,
                "created_at": "2026-08-04T00:00:01+00:00",
            }
        ],
    }


async def test_profile_marks_only_the_configured_authenticated_uuid_as_demo(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ARTHA_DEMO_ACCOUNT_USER_ID", USER_ID)

    result = await profile(
        cast(SupabaseRestClient, FakeProductionClient()),
        AuthContext(user_id=USER_ID),
    )

    assert result["is_demo"] is True


async def test_sample_only_policy_blocks_personal_capture_before_model_call(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ARTHA_AI_DATA_POLICY", "sample_only")

    def unexpected_assistant() -> None:
        raise AssertionError("personal text must not reach the configured model")

    monkeypatch.setattr(
        "artha_api.production_routes.LocalFinancialAssistant", unexpected_assistant
    )

    with pytest.raises(HTTPException) as error:
        await parse_draft(
            ParseRequest(text="Paid 500 for lunch", timezone="Asia/Kolkata"),
            cast(SupabaseRestClient, FakeProductionClient()),
            AuthContext(user_id=USER_ID),
        )

    assert error.value.status_code == 403
    assert error.value.detail == (
        "AI features are not enabled for personal financial data in this "
        "deployment; use manual entry."
    )


async def test_sample_only_policy_allows_the_configured_demo_uuid(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ARTHA_AI_DATA_POLICY", "sample_only")
    monkeypatch.setenv("ARTHA_DEMO_ACCOUNT_USER_ID", USER_ID)

    async def clarify(
        _self: LocalFinancialAssistant,
        _message: str,
        _context: object,
    ) -> CaptureInterpretationResponse:
        return CaptureInterpretationResponse(
            provider=LlmProvider.GEMINI,
            model="test-model",
            result=CaptureClarification(
                outcome="clarify",
                question="Which account should this use?",
                missing=["source_account_id"],
            ),
        )

    monkeypatch.setattr(LocalFinancialAssistant, "interpret_capture", clarify)

    result = await parse_draft(
        ParseRequest(text="Paid 500 for lunch", timezone="Asia/Kolkata"),
        cast(SupabaseRestClient, FakeProductionClient()),
        AuthContext(user_id=USER_ID),
    )

    assert result["outcome"] == "clarification"
    assert result["missing_field"] == "source_account_id"


async def test_sample_only_policy_blocks_personal_chat_and_tag_before_model_call(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ARTHA_AI_DATA_POLICY", "sample_only")

    def unexpected_assistant() -> None:
        raise AssertionError("personal text must not reach the configured model")

    monkeypatch.setattr(
        "artha_api.production_routes.LocalFinancialAssistant", unexpected_assistant
    )

    with pytest.raises(HTTPException) as chat_error:
        await assistant_chat(
            AssistantChatRequest(message="Show my spending"),
            cast(SupabaseRestClient, FakeProductionClient()),
            AuthContext(user_id=USER_ID),
        )
    with pytest.raises(HTTPException) as tag_error:
        await assistant_tag_suggestion(
            ProductionTagSuggestionRequest(
                description="Food purchase",
                amount_paise=12_000,
                direction="expense",
            ),
            cast(SupabaseRestClient, FakeProductionClient()),
            AuthContext(user_id=USER_ID),
        )

    assert chat_error.value.status_code == 403
    assert tag_error.value.status_code == 403


async def test_assistant_status_exposes_policy_without_demo_uuid(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ARTHA_AI_DATA_POLICY", "sample_only")
    monkeypatch.setenv("ARTHA_DEMO_ACCOUNT_USER_ID", USER_ID)

    class StatusAssistant:
        async def status(self) -> AssistantStatus:
            return AssistantStatus(
                configured=True,
                provider=LlmProvider.GEMINI,
                model="test-model",
                available=True,
                active_provider=LlmProvider.GEMINI,
                ollama_fallback_enabled=False,
                detail="ready",
            )

    monkeypatch.setattr(
        "artha_api.production_routes.LocalFinancialAssistant", StatusAssistant
    )

    result = await assistant_status(AuthContext(user_id=USER_ID))

    assert result.data_policy == "sample_only"
    assert result.personal_data_enabled is False
    assert result.is_demo is True
    assert "demo_user_id" not in result.model_dump(mode="json")


async def test_parse_draft_returns_model_clarification_without_inventing_a_draft(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def clarify(
        _self: LocalFinancialAssistant,
        _message: str,
        _context: object,
    ) -> CaptureInterpretationResponse:
        return CaptureInterpretationResponse(
            provider=LlmProvider.GEMINI,
            model="test-model",
            result=CaptureClarification(
                outcome="clarify",
                question="untrusted model wording",
                missing=["source_account_id"],
                amount_paise=54_000,
                kind="expense",
                description="Zomato",
            ),
        )

    monkeypatch.setattr(LocalFinancialAssistant, "interpret_capture", clarify)

    accounts = [
        {
            "id": ACCOUNT_ID,
            "name": "HDFC UPI",
            "account_type": "bank",
            "currency": "INR",
            "opening_balance_paise": 0,
            "credit_limit_paise": None,
            "statement_day": None,
            "payment_due_day": None,
            "is_archived": False,
            "created_at": "2026-08-04T00:00:00+00:00",
        },
        {
            "id": DESTINATION_ACCOUNT_ID,
            "name": "SBI Cashback Card",
            "account_type": "credit_card",
            "currency": "INR",
            "opening_balance_paise": 0,
            "credit_limit_paise": 100_000,
            "statement_day": 5,
            "payment_due_day": 25,
            "is_archived": False,
            "created_at": "2026-08-04T00:00:01+00:00",
        },
    ]
    result = await parse_draft(
        ParseRequest(text="Paid 540 at Zomato", timezone="Asia/Kolkata"),
        cast(SupabaseRestClient, FakeProductionClient(accounts=accounts)),
        AuthContext(user_id=USER_ID),
    )

    assert result == {
        "outcome": "clarification",
        "source_text": "Paid 540 at Zomato",
        "understood": {
            "amount_paise": 54_000,
            "kind": "expense",
            "merchant": "Zomato",
        },
        "missing_field": "source_account_id",
        "question": "How did you pay for Zomato?",
        "explanation": (
            "Choose one so Artha updates the correct balance. Nothing has been saved."
        ),
        "choices": [
            {
                "id": ACCOUNT_ID,
                "label": "HDFC UPI",
                "answer": "paid from HDFC UPI",
            },
            {
                "id": DESTINATION_ACCOUNT_ID,
                "label": "SBI Cashback Card",
                "answer": "paid from SBI Cashback Card",
            },
        ],
        "warnings": [],
        "parser_source": "gemini:test-model",
    }


def test_category_clarification_points_to_the_form_without_fake_choices() -> None:
    result = production_routes.capture_clarification_response(
        CaptureClarification(
            outcome="clarify",
            question="untrusted model wording",
            missing=["category_id"],
            amount_paise=54_000,
            kind="expense",
            description="Zomato",
        ),
        source_text="Paid 540 at Zomato from HDFC UPI",
        accounts=[],
        parser_source="gemini:test-model",
    )

    assert result["missing_field"] == "category_id"
    assert result["choices"] == []
    assert result["explanation"] == (
        "Open the form below and choose a category. Nothing has been saved."
    )

    kind_result = production_routes.capture_clarification_response(
        CaptureClarification(
            outcome="clarify",
            question="untrusted model wording",
            missing=["kind"],
            amount_paise=54_000,
            description="Zomato",
        ),
        source_text="Zomato 540",
        accounts=[],
        parser_source="gemini:test-model",
    )
    assert kind_result["choices"] == []
    assert kind_result["explanation"] == (
        "Open the form below and choose the movement type. Nothing has been saved."
    )


async def test_parse_draft_enriches_reviewable_transaction_metadata(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def interpret(
        _self: LocalFinancialAssistant,
        _message: str,
        _context: object,
    ) -> CaptureInterpretationResponse:
        return CaptureInterpretationResponse(
            provider=LlmProvider.GEMINI,
            model="test-model",
            result=CaptureDraftInterpretation(
                outcome="draft",
                kind="expense",
                amount_paise=68_000,
                description="Burger King",
                platform="Zomato",
                subcategory=None,
                attributes=[
                    ModelAttribute(
                        key="meal_occasion",
                        value="Dinner",
                        source="user_explicit",
                        confidence=0.99,
                    )
                ],
                tags=[
                    ModelTag(
                        name="Date Night",
                        source="user_explicit",
                        confidence=0.98,
                    )
                ],
                field_evidence=[
                    ModelFieldEvidence(
                        field="merchant",
                        source="user_explicit",
                        confidence=0.99,
                    ),
                    ModelFieldEvidence(
                        field="platform",
                        source="user_explicit",
                        confidence=0.99,
                    ),
                ],
                category_id=None,
                category_name=None,
                source_account_id=ACCOUNT_ID,
                destination_account_id=None,
                member_ids=[],
                split_equally=False,
                occurred_on="2026-08-08",
                confidence=0.96,
                warnings=[],
            ),
        )

    monkeypatch.setattr(LocalFinancialAssistant, "interpret_capture", interpret)
    categories = [
        {
            "id": CATEGORY_ID,
            "name": "Food & Dining",
            "category_type": "expense",
            "is_archived": False,
        }
    ]

    result = await parse_draft(
        ParseRequest(
            text=(
                "Paid 680 for dinner at Burger King via Zomato from Known Bank, "
                "date night"
            ),
            timezone="Asia/Kolkata",
        ),
        cast(
            SupabaseRestClient,
            FakeProductionClient(categories=categories, merchant_rules=[]),
        ),
        AuthContext(user_id=USER_ID),
    )

    draft = result["draft"]
    assert {
        key: draft[key]
        for key in (
            "description",
            "category",
            "platform",
            "subcategory",
            "category_suggestion",
            "metadata",
            "tag_suggestions",
        )
    } == {
            "description": "Burger King",
            "category": "Food & Dining",
            "platform": "Zomato",
            "subcategory": "Fast Food",
            "category_suggestion": {
                "source": "safe_catalog",
                "confidence": 1.0,
                "reason": "Burger King is in Artha's food merchant catalog.",
            },
            "metadata": {
                "version": 1,
                "evidence": {
                    "merchant": {
                        "source": "user_explicit",
                        "confidence": 0.99,
                        "review_status": "needs_review",
                    },
                    "platform": {
                        "source": "user_explicit",
                        "confidence": 0.99,
                        "review_status": "needs_review",
                    },
                    "category": {
                        "source": "safe_catalog",
                        "confidence": 1.0,
                        "review_status": "needs_review",
                    },
                    "subcategory": {
                        "source": "safe_catalog",
                        "confidence": 1.0,
                        "review_status": "needs_review",
                    },
                },
                "attributes": [
                    {
                        "key": "meal_occasion",
                        "value": "Dinner",
                        "source": "user_explicit",
                        "confidence": 0.99,
                        "review_status": "needs_review",
                    },
                    {
                        "key": "order_channel",
                        "value": "Delivery",
                        "source": "safe_catalog",
                        "confidence": 1.0,
                        "review_status": "needs_review",
                    },
                ],
            },
            "tag_suggestions": [
                {
                    "name": "Date Night",
                    "normalized_name": "date night",
                    "source": "user_explicit",
                    "confidence": 0.98,
                    "review_status": "needs_review",
                }
            ],
        }


async def test_parse_draft_returns_sanitized_503_when_ai_is_unavailable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def unavailable(
        _self: LocalFinancialAssistant,
        _message: str,
        _context: object,
    ) -> None:
        return None

    monkeypatch.setattr(LocalFinancialAssistant, "interpret_capture", unavailable)

    with pytest.raises(HTTPException) as error:
        await parse_draft(
            ParseRequest(text="self transfer 25k ICICI -> HDFC", timezone="Asia/Kolkata"),
            cast(SupabaseRestClient, FakeProductionClient()),
            AuthContext(user_id=USER_ID),
        )

    assert error.value.status_code == 503
    assert error.value.detail == (
        "Automatic interpretation is temporarily unavailable; "
        "review the details manually."
    )


def test_production_draft_rejects_inexact_split_total() -> None:
    with pytest.raises(ValidationError, match="must add up"):
        ProductionDraft(
            kind="expense",
            amount_paise=10_000,
            description="Groceries",
            category="Groceries",
            personal_share_paise=5_000,
            splits=[ProductionSplit(member_id=MEMBER_ID, amount_paise=4_000)],
            source_account_id=ACCOUNT_ID,
        )


async def test_production_transfer_uses_atomic_transfer_rpc() -> None:
    fake = FakeProductionClient()
    draft = ProductionDraft(
        kind="transfer",
        amount_paise=2_500_000,
        description="Self transfer",
        category="Transfer",
        personal_share_paise=2_500_000,
        source_account_id=ACCOUNT_ID,
        destination_account_id=DESTINATION_ACCOUNT_ID,
    )

    result = await confirm_transaction(
        draft,
        cast(SupabaseRestClient, fake),
        AuthContext(user_id=USER_ID),
        "transfer-idempotency-key",
    )

    assert fake.transfer_payload is not None
    assert fake.transfer_payload["p_from_account_id"] == ACCOUNT_ID
    assert fake.transfer_payload["p_to_account_id"] == DESTINATION_ACCOUNT_ID
    assert fake.transfer_payload["p_amount_paise"] == 2_500_000
    assert fake.transfer_payload["p_note"] == "Self transfer"
    assert result["kind"] == "transfer"
    assert result["personal_share_paise"] == 2_500_000


def test_production_transfer_rejects_same_account() -> None:
    with pytest.raises(ValidationError, match="must be different"):
        ProductionDraft(
            kind="transfer",
            amount_paise=2_500_000,
            description="Self transfer",
            category="Transfer",
            personal_share_paise=2_500_000,
            source_account_id=ACCOUNT_ID,
            destination_account_id=ACCOUNT_ID,
        )


def test_member_balance_projection_handles_owner_and_member_paid_expenses() -> None:
    rows = [
        {
            "direction": "expense",
            "paid_by_member_id": OWNER_ID,
            "transaction_splits": [
                {"member_id": OWNER_ID, "amount_paise": 6_000},
                {"member_id": MEMBER_ID, "amount_paise": 4_000},
            ],
        },
        {
            "direction": "expense",
            "paid_by_member_id": MEMBER_ID,
            "transaction_splits": [
                {"member_id": OWNER_ID, "amount_paise": 2_500},
                {"member_id": MEMBER_ID, "amount_paise": 2_500},
            ],
        },
    ]
    members = [
        {"id": OWNER_ID, "display_name": "Owner"},
        {"id": MEMBER_ID, "display_name": "Family member"},
    ]

    settlements = [{
        "payer_member_id": MEMBER_ID,
        "payee_member_id": OWNER_ID,
        "amount_paise": 1_000,
    }]

    assert member_balances(rows, members, OWNER_ID, settlements) == [
        {
            "member_id": MEMBER_ID,
            "member_name": "Family member",
            "balance_paise": 500,
            "status": "owes you",
        }
    ]


async def test_shared_balance_settlement_uses_one_atomic_database_command() -> None:
    fake = FakeProductionClient()

    result = await production_routes.create_settlement(
        production_routes.ProductionSettlementRequest(
            member_id=UUID(MEMBER_ID),
            account_id=UUID(ACCOUNT_ID),
            amount_paise=2_500,
            settled_at=datetime.fromisoformat("2026-08-10T12:00:00+00:00"),
            note="Partial repayment",
        ),
        cast(SupabaseRestClient, fake),
        AuthContext(user_id=USER_ID),
        "settlement-key-0001",
    )
    replay = await production_routes.create_settlement(
        production_routes.ProductionSettlementRequest(
            member_id=UUID(MEMBER_ID),
            account_id=UUID(ACCOUNT_ID),
            amount_paise=2_500,
            settled_at=datetime.fromisoformat("2026-08-10T12:00:00+00:00"),
            note="Partial repayment",
        ),
        cast(SupabaseRestClient, fake),
        AuthContext(user_id=USER_ID),
        "settlement-key-0001",
    )

    assert fake.settlement_payload == {
        "p_household_id": HOUSEHOLD_ID,
        "p_member_id": MEMBER_ID,
        "p_account_id": ACCOUNT_ID,
        "p_amount_paise": 2_500,
        "p_settled_at": "2026-08-10T12:00:00+00:00",
        "p_idempotency_key": "settlement-key-0001",
        "p_note": "Partial repayment",
    }
    assert result["balance_paise"] == 1_500
    assert replay == result
    assert fake.rpc_names.count("settle_member_balance") == 2


async def test_transaction_history_pages_logical_activity_in_database() -> None:
    fake = FakeProductionClient()

    result = await list_transactions(
        cast(SupabaseRestClient, fake),
        AuthContext(user_id=USER_ID),
        limit=1,
    )

    assert fake.activity_payload == {
        "p_household_id": HOUSEHOLD_ID,
        "p_limit": 2,
        "p_before_occurred_at": None,
        "p_before_created_at": None,
        "p_before_id": None,
    }
    assert result["items"][0]["kind"] == "transfer"
    assert result["items"][0]["source_account_id"] == ACCOUNT_ID
    assert result["items"][0]["destination_account_id"] == DESTINATION_ACCOUNT_ID
    assert result["items"][0]["account_delta_paise"] == 0
    assert result["next_cursor"] == {
        "occurred_at": "2026-08-04T12:00:00+00:00",
        "created_at": "2026-08-04T12:00:00+00:00",
        "id": TRANSACTION_ID,
    }


async def test_transaction_search_runs_inside_database_over_notes() -> None:
    fake = FakeProductionClient()

    result = await list_transactions(
        cast(SupabaseRestClient, fake),
        AuthContext(user_id=USER_ID),
        limit=50,
        q="team dinner",
    )

    assert fake.activity_payload == {
        "p_household_id": HOUSEHOLD_ID,
        "p_query": "team dinner",
        "p_limit": 50,
    }
    assert result["items"][0]["notes"] == "Team dinner"
    assert result["next_cursor"] is None


async def test_production_transaction_correction_uses_atomic_rpc_and_returns_replacement() -> None:
    fake = FakeProductionClient()
    payload = production_routes.ProductionCorrectionRequest(
        replacement=ProductionDraft(
            kind="transfer",
            amount_paise=2_500_000,
            description="Move to savings",
            category=None,
            personal_share_paise=2_500_000,
            source_account_id=ACCOUNT_ID,
            destination_account_id=DESTINATION_ACCOUNT_ID,
            occurred_at="2026-08-09T12:00:00+00:00",
            notes="Corrected transfer",
        ),
        reason="Corrected the destination account",
    )

    result = await production_routes.update_transaction(
        UUID(TRANSACTION_ID),
        payload,
        cast(SupabaseRestClient, fake),
        AuthContext(user_id=USER_ID),
        "daily-correction-key",
    )
    fake.categories[0]["is_archived"] = True
    replay = await production_routes.update_transaction(
        UUID(TRANSACTION_ID),
        payload,
        cast(SupabaseRestClient, fake),
        AuthContext(user_id=USER_ID),
        "daily-correction-key",
    )

    assert fake.correction_payload == {
        "p_household_id": HOUSEHOLD_ID,
        "p_transaction_id": TRANSACTION_ID,
        "p_replacement": {
            "kind": "transfer",
            "source_account_id": ACCOUNT_ID,
            "destination_account_id": DESTINATION_ACCOUNT_ID,
            "amount_paise": 2_500_000,
            "currency": "INR",
            "occurred_at": "2026-08-09T12:00:00Z",
            "note": "Corrected transfer",
        },
        "p_reason": "Corrected the destination account",
        "p_idempotency_key": "daily-correction-key",
    }
    assert result["id"] == TRANSACTION_ID
    assert result["kind"] == "transfer"
    assert result == replay
    assert result["created_at"] == "2026-08-10T12:00:00+00:00"
    assert result["updated_at"] == "2026-08-10T12:00:00+00:00"


def test_production_correction_requires_an_explicit_date_for_exact_replay() -> None:
    with pytest.raises(ValidationError, match="correction date is required"):
        production_routes.ProductionCorrectionRequest(
            replacement=ProductionDraft(
                kind="expense",
                amount_paise=1_000,
                description="Coffee",
                category="Groceries",
                personal_share_paise=1_000,
                source_account_id=ACCOUNT_ID,
            ),
            reason="Corrected details",
        )


async def test_cashflow_correction_replay_resolves_the_original_archived_category() -> None:
    fake = FakeProductionClient(categories=[
        {
            "id": "00000000-0000-0000-0000-000000000001",
            "name": "Groceries",
            "category_type": "expense",
            "is_archived": True,
        },
        {
            "id": CATEGORY_ID,
            "name": "Groceries",
            "category_type": "expense",
            "is_archived": False,
        },
    ])
    payload = production_routes.ProductionCorrectionRequest(
        replacement=ProductionDraft(
            kind="expense",
            amount_paise=1_000,
            description="Coffee",
            category="Groceries",
            personal_share_paise=1_000,
            source_account_id=ACCOUNT_ID,
            occurred_at="2026-08-09T12:00:00+00:00",
        ),
        reason="Corrected merchant",
    )

    first = await production_routes.update_transaction(
        UUID(TRANSACTION_ID), payload, cast(SupabaseRestClient, fake),
        AuthContext(user_id=USER_ID), "daily-cashflow-correction-key",
    )
    replay = await production_routes.update_transaction(
        UUID(TRANSACTION_ID), payload, cast(SupabaseRestClient, fake),
        AuthContext(user_id=USER_ID), "daily-cashflow-correction-key",
    )

    assert replay == first
    assert fake.correction_payload is not None
    assert fake.correction_payload["p_replacement"]["category_name"] == "Groceries"
    assert "category_id" not in fake.correction_payload["p_replacement"]


async def test_production_transaction_removal_uses_audited_void_rpc() -> None:
    fake = FakeProductionClient()

    result = await production_routes.delete_transaction(
        UUID(TRANSACTION_ID),
        production_routes.ProductionVoidRequest(reason="Duplicate transaction"),
        cast(SupabaseRestClient, fake),
        AuthContext(user_id=USER_ID),
        "daily-removal-key",
    )

    assert fake.void_payload == {
        "p_household_id": HOUSEHOLD_ID,
        "p_activity_id": TRANSACTION_ID,
        "p_reason": "Duplicate transaction",
        "p_idempotency_key": "daily-removal-key",
    }
    assert result["id"] == TRANSACTION_ID
    assert result["deleted"] is True
    assert result["status"] == "voided"
