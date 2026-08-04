from __future__ import annotations

from typing import Any, cast

import pytest
from pydantic import ValidationError

from hisab_api.auth import AuthContext
from hisab_api.production_routes import (
    ProductionDraft,
    ProductionSplit,
    confirm_transaction,
    member_balances,
)
from hisab_api.supabase_rest import SupabaseRestClient

HOUSEHOLD_ID = "00000000-0000-0000-0000-000000000100"
OWNER_ID = "00000000-0000-0000-0000-000000000101"
MEMBER_ID = "00000000-0000-0000-0000-000000000102"
ACCOUNT_ID = "00000000-0000-0000-0000-000000000103"
CATEGORY_ID = "00000000-0000-0000-0000-000000000104"
USER_ID = "00000000-0000-0000-0000-000000000105"
TRANSACTION_ID = "00000000-0000-0000-0000-000000000106"


class FakeProductionClient:
    def __init__(self) -> None:
        self.confirm_payload: dict[str, Any] | None = None

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
