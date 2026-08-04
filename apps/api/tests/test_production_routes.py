from __future__ import annotations

from typing import Any, cast

import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from artha_api.assistant import (
    CaptureClarification,
    CaptureInterpretationResponse,
    LlmProvider,
    LocalFinancialAssistant,
)
from artha_api.auth import AuthContext
from artha_api.production_routes import (
    ProductionDraft,
    ProductionSplit,
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
            provider=LlmProvider.GROQ,
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
