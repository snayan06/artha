from __future__ import annotations

from typing import Any, cast

import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from artha_api import production_routes
from artha_api.assistant import (
    AssistantChatRequest,
    CaptureClarification,
    CaptureInterpretationResponse,
    LlmProvider,
    LocalFinancialAssistant,
    TagSuggestion,
    TagSuggestionRequest,
    TagSuggestionResponse,
)
from artha_api.auth import AuthContext
from artha_api.production_routes import (
    ProductionDraft,
    ProductionSplit,
    ProductionTagSuggestionRequest,
    assistant_chat,
    assistant_tag_suggestion,
    confirm_transaction,
    list_transactions,
    member_balances,
    parse_draft,
    profile,
)
from artha_api.schemas import ParseRequest
from artha_api.supabase_rest import SupabaseRestClient

HOUSEHOLD_ID = "00000000-0000-0000-0000-000000000100"
OWNER_ID = "00000000-0000-0000-0000-000000000101"
MEMBER_ID = "00000000-0000-0000-0000-000000000102"
ACCOUNT_ID = "00000000-0000-0000-0000-000000000103"
DESTINATION_ACCOUNT_ID = "00000000-0000-0000-0000-000000000107"
CATEGORY_ID = "00000000-0000-0000-0000-000000000104"
USER_ID = "00000000-0000-0000-0000-000000000105"
TRANSACTION_ID = "00000000-0000-0000-0000-000000000106"


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
            {"id": "income", "name": "Salary", "kind": "income"},
            {"id": "both", "name": "Other", "kind": "both"},
        ],
    }
    assert client.params_by_path["accounts"] == expect_capture_scope(
        "id,name,account_type,currency,opening_balance_paise,credit_limit_paise,"
        "statement_day,payment_due_day,is_archived,created_at",
        order="created_at.asc,id.asc",
    )
    assert client.params_by_path["categories"] == expect_capture_scope(
        "id,name,category_type"
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
    def __init__(self) -> None:
        self.confirm_payload: dict[str, Any] | None = None
        self.transfer_payload: dict[str, Any] | None = None
        self.activity_payload: dict[str, Any] | None = None

    async def rpc(self, name: str, payload: dict[str, Any] | None = None) -> Any:
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
        if name == "get_account_balances":
            return [{"account_id": ACCOUNT_ID, "balance_paise": 50_000}]
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
            return [{"id": CATEGORY_ID, "name": "Groceries", "category_type": "expense"}]
        if path == "accounts":
            return [{
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
        "select": "id,name,category_type",
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


async def test_profile_hydrates_server_owned_household_and_participants() -> None:
    fake = FakeProductionClient()

    result = await profile(
        cast(SupabaseRestClient, fake),
        AuthContext(user_id=USER_ID),
    )

    assert result == {
        "display_name": "Owner",
        "household_name": "Test household",
        "members": [
            {
                "id": MEMBER_ID,
                "name": "Family member",
                "is_archived": False,
                "created_at": "2026-08-04T00:00:01+00:00",
            }
        ],
    }


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
                question="Which account should this use?",
                missing=["source_account_id"],
            ),
        )

    monkeypatch.setattr(LocalFinancialAssistant, "interpret_capture", clarify)

    with pytest.raises(HTTPException) as error:
        await parse_draft(
            ParseRequest(text="25k", timezone="Asia/Kolkata"),
            cast(SupabaseRestClient, FakeProductionClient()),
            AuthContext(user_id=USER_ID),
        )

    assert error.value.status_code == 422
    assert error.value.detail == "Which account should this use?"


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

    assert member_balances(rows, members, OWNER_ID) == [
        {
            "member_id": MEMBER_ID,
            "member_name": "Family member",
            "balance_paise": 1_500,
            "status": "owes you",
        }
    ]


async def test_transaction_history_pages_logical_activity_in_database() -> None:
    fake = FakeProductionClient()

    result = await list_transactions(
        cast(SupabaseRestClient, fake),
        AuthContext(user_id=USER_ID),
        limit=25,
        offset=50,
    )

    assert fake.activity_payload == {
        "p_household_id": HOUSEHOLD_ID,
        "p_limit": 25,
        "p_offset": 50,
    }
    assert result[0]["kind"] == "transfer"
    assert result[0]["source_account_id"] == ACCOUNT_ID
    assert result[0]["destination_account_id"] == DESTINATION_ACCOUNT_ID
    assert result[0]["account_delta_paise"] == 0
