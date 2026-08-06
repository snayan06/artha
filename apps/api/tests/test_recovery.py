from __future__ import annotations

from copy import deepcopy
from typing import Any, cast

import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from artha_api.auth import AuthContext
from artha_api.production_routes import (
    export_recovery_bundle,
    preview_recovery_bundle,
    restore_recovery_bundle,
)
from artha_api.recovery import RecoveryBundle
from artha_api.supabase_rest import SupabaseRestClient

HOUSEHOLD_ID = "00000000-0000-0000-0000-000000000001"
USER_ID = "00000000-0000-0000-0000-000000000002"
OWNER_ID = "00000000-0000-0000-0000-000000000003"
MEMBER_ID = "00000000-0000-0000-0000-000000000004"
ACCOUNT_ID = "00000000-0000-0000-0000-000000000005"
CASH_ID = "00000000-0000-0000-0000-000000000006"
CATEGORY_ID = "00000000-0000-0000-0000-000000000007"
EXPENSE_ID = "00000000-0000-0000-0000-000000000008"
TRANSFER_OUT_ID = "00000000-0000-0000-0000-000000000009"
TRANSFER_IN_ID = "00000000-0000-0000-0000-000000000010"
TRANSFER_ID = "00000000-0000-0000-0000-000000000011"
SETTLEMENT_TX_ID = "00000000-0000-0000-0000-000000000012"
SETTLEMENT_ID = "00000000-0000-0000-0000-000000000013"
RULE_ID = "00000000-0000-0000-0000-000000000014"
NOW = "2026-08-06T01:02:03+00:00"


def valid_bundle_payload() -> dict[str, Any]:
    return {
        "format": "artha-recovery",
        "schema_version": 1,
        "exported_at": NOW,
        "household": {"name": "Fictional household"},
        "profile": {"display_name": "Fictional owner"},
        "members": [
            {
                "source_id": OWNER_ID,
                "display_name": "Fictional owner",
                "member_type": "user",
                "role": "owner",
                "is_active": True,
            },
            {
                "source_id": MEMBER_ID,
                "display_name": "Fictional member",
                "member_type": "participant",
                "role": "member",
                "is_active": True,
            },
        ],
        "accounts": [
            {
                "source_id": ACCOUNT_ID,
                "name": "Fictional Bank",
                "account_type": "bank",
                "currency": "INR",
                "opening_balance_paise": 100_000,
                "credit_limit_paise": None,
                "statement_day": None,
                "payment_due_day": None,
                "is_archived": False,
                "created_at": NOW,
            },
            {
                "source_id": CASH_ID,
                "name": "Fictional Cash",
                "account_type": "cash",
                "currency": "INR",
                "opening_balance_paise": 5_000,
                "credit_limit_paise": None,
                "statement_day": None,
                "payment_due_day": None,
                "is_archived": False,
                "created_at": NOW,
            },
        ],
        "categories": [
            {
                "source_id": CATEGORY_ID,
                "name": "Fictional groceries",
                "category_type": "expense",
                "icon": "basket",
                "is_archived": False,
                "created_at": NOW,
            }
        ],
        "transactions": [
            {
                "source_id": EXPENSE_ID,
                "account_source_id": ACCOUNT_ID,
                "category_source_id": CATEGORY_ID,
                "paid_by_member_source_id": OWNER_ID,
                "direction": "expense",
                "amount_paise": 1_000,
                "currency": "INR",
                "occurred_at": NOW,
                "merchant": "Fictional market",
                "note": None,
                "status": "posted",
                "metadata": {"source": "manual", "reviewed": True},
                "created_at": NOW,
                "voided_at": None,
            },
            {
                "source_id": TRANSFER_OUT_ID,
                "account_source_id": ACCOUNT_ID,
                "category_source_id": None,
                "paid_by_member_source_id": None,
                "direction": "transfer_out",
                "amount_paise": 2_000,
                "currency": "INR",
                "occurred_at": NOW,
                "merchant": None,
                "note": "Fictional transfer",
                "status": "posted",
                "metadata": {},
                "created_at": NOW,
                "voided_at": None,
            },
            {
                "source_id": TRANSFER_IN_ID,
                "account_source_id": CASH_ID,
                "category_source_id": None,
                "paid_by_member_source_id": None,
                "direction": "transfer_in",
                "amount_paise": 2_000,
                "currency": "INR",
                "occurred_at": NOW,
                "merchant": None,
                "note": "Fictional transfer",
                "status": "posted",
                "metadata": {},
                "created_at": NOW,
                "voided_at": None,
            },
            {
                "source_id": SETTLEMENT_TX_ID,
                "account_source_id": ACCOUNT_ID,
                "category_source_id": None,
                "paid_by_member_source_id": None,
                "direction": "settlement_out",
                "amount_paise": 400,
                "currency": "INR",
                "occurred_at": NOW,
                "merchant": None,
                "note": "Fictional settlement",
                "status": "posted",
                "metadata": {},
                "created_at": NOW,
                "voided_at": None,
            },
        ],
        "splits": [
            {
                "transaction_source_id": EXPENSE_ID,
                "member_source_id": OWNER_ID,
                "amount_paise": 600,
            },
            {
                "transaction_source_id": EXPENSE_ID,
                "member_source_id": MEMBER_ID,
                "amount_paise": 400,
            },
        ],
        "transfers": [
            {
                "source_id": TRANSFER_ID,
                "out_transaction_source_id": TRANSFER_OUT_ID,
                "in_transaction_source_id": TRANSFER_IN_ID,
                "created_at": NOW,
            }
        ],
        "settlements": [
            {
                "source_id": SETTLEMENT_ID,
                "payer_member_source_id": MEMBER_ID,
                "payee_member_source_id": OWNER_ID,
                "account_source_id": ACCOUNT_ID,
                "transaction_source_id": SETTLEMENT_TX_ID,
                "account_direction": "settlement_out",
                "amount_paise": 400,
                "currency": "INR",
                "settled_at": NOW,
                "note": "Fictional settlement",
                "created_at": NOW,
            }
        ],
        "merchant_rules": [
            {
                "source_id": RULE_ID,
                "match_type": "contains",
                "merchant_pattern": "fictional market",
                "category_source_id": CATEGORY_ID,
                "account_source_id": ACCOUNT_ID,
                "priority": 100,
                "is_active": True,
                "created_at": NOW,
            }
        ],
        "audit_events": [
            {
                "source_id": 1,
                "entity_type": "account",
                "entity_source_id": ACCOUNT_ID,
                "action": "created",
                "payload": {"fixture": True},
                "occurred_at": NOW,
            }
        ],
    }


def valid_bundle() -> RecoveryBundle:
    return RecoveryBundle.model_validate(valid_bundle_payload())


def test_bundle_summary_is_complete_and_canonical() -> None:
    first_payload = valid_bundle_payload()
    second_payload = deepcopy(first_payload)
    second_payload["transactions"][0]["metadata"] = {
        "reviewed": True,
        "source": "manual",
    }

    first = RecoveryBundle.model_validate(first_payload)
    second = RecoveryBundle.model_validate(second_payload)

    assert first.summary() == {
        "sha256": second.summary()["sha256"],
        "members": 2,
        "accounts": 2,
        "categories": 1,
        "transactions": 4,
        "splits": 2,
        "transfers": 1,
        "settlements": 1,
        "merchant_rules": 1,
        "audit_events": 1,
    }


@pytest.mark.parametrize(
    ("path", "value", "message"),
    [
        (
            ("transactions", 0, "account_source_id"),
            "00000000-0000-0000-0000-000000000099",
            "unknown account",
        ),
        (
            ("splits", 0, "member_source_id"),
            "00000000-0000-0000-0000-000000000099",
            "unknown transaction or member",
        ),
        (
            ("settlements", 0, "payer_member_source_id"),
            "00000000-0000-0000-0000-000000000099",
            "unknown member",
        ),
        (
            ("merchant_rules", 0, "category_source_id"),
            "00000000-0000-0000-0000-000000000099",
            "unknown category",
        ),
    ],
)
def test_bundle_rejects_open_references(
    path: tuple[str, int, str], value: str, message: str
) -> None:
    payload = valid_bundle_payload()
    collection, index, field = path
    payload[collection][index][field] = value

    with pytest.raises(ValidationError, match=message):
        RecoveryBundle.model_validate(payload)


def test_bundle_rejects_duplicate_source_ids_and_split_pairs() -> None:
    duplicate_account = valid_bundle_payload()
    duplicate_account["accounts"][1]["source_id"] = ACCOUNT_ID
    with pytest.raises(ValidationError, match="duplicate account source IDs"):
        RecoveryBundle.model_validate(duplicate_account)

    duplicate_split = valid_bundle_payload()
    duplicate_split["splits"].append(deepcopy(duplicate_split["splits"][0]))
    with pytest.raises(ValidationError, match="duplicate transaction split"):
        RecoveryBundle.model_validate(duplicate_split)


def test_bundle_rejects_invalid_owner_and_active_name_shapes() -> None:
    inactive_owner = valid_bundle_payload()
    inactive_owner["members"][0]["is_active"] = False
    with pytest.raises(ValidationError, match="exactly one active owner"):
        RecoveryBundle.model_validate(inactive_owner)

    second_user = valid_bundle_payload()
    second_user["members"][1].update({"member_type": "user", "role": "member"})
    with pytest.raises(ValidationError, match="only one owner and participant"):
        RecoveryBundle.model_validate(second_user)

    mismatched_profile = valid_bundle_payload()
    mismatched_profile["profile"]["display_name"] = "Different owner"
    with pytest.raises(ValidationError, match="owner and profile display names must match"):
        RecoveryBundle.model_validate(mismatched_profile)

    duplicate_names = valid_bundle_payload()
    duplicate_names["accounts"][1]["name"] = " fictional   bank "
    with pytest.raises(ValidationError, match="duplicate active account names"):
        RecoveryBundle.model_validate(duplicate_names)

    blank_household = valid_bundle_payload()
    blank_household["household"]["name"] = "   "
    with pytest.raises(ValidationError, match="cannot be blank"):
        RecoveryBundle.model_validate(blank_household)


def test_bundle_rejects_invalid_cashflow_and_transfer_shapes() -> None:
    inexact_splits = valid_bundle_payload()
    inexact_splits["splits"][1]["amount_paise"] = 399
    with pytest.raises(ValidationError, match="splits must equal"):
        RecoveryBundle.model_validate(inexact_splits)

    mismatched_transfer = valid_bundle_payload()
    mismatched_transfer["transactions"][2]["amount_paise"] = 2_001
    with pytest.raises(ValidationError, match="linked transfer facts must match"):
        RecoveryBundle.model_validate(mismatched_transfer)

    same_account = valid_bundle_payload()
    same_account["transactions"][2]["account_source_id"] = ACCOUNT_ID
    with pytest.raises(ValidationError, match="transfer accounts must be different"):
        RecoveryBundle.model_validate(same_account)


def test_bundle_rejects_invalid_settlement_linkage() -> None:
    partial = valid_bundle_payload()
    partial["settlements"][0]["account_direction"] = None
    with pytest.raises(ValidationError, match="linkage must be complete"):
        RecoveryBundle.model_validate(partial)

    mismatch = valid_bundle_payload()
    mismatch["settlements"][0]["amount_paise"] = 401
    with pytest.raises(ValidationError, match="linked settlement facts must match"):
        RecoveryBundle.model_validate(mismatch)


def test_bundle_rejects_positive_card_debt_and_naive_timestamps() -> None:
    positive_card = valid_bundle_payload()
    positive_card["accounts"][0].update(
        {
            "account_type": "credit_card",
            "opening_balance_paise": 100,
            "credit_limit_paise": 10_000,
            "statement_day": 5,
            "payment_due_day": 25,
        }
    )
    with pytest.raises(ValidationError, match="cannot be positive"):
        RecoveryBundle.model_validate(positive_card)

    naive_timestamp = valid_bundle_payload()
    naive_timestamp["exported_at"] = "2026-08-06T01:02:03"
    with pytest.raises(ValidationError, match="must include a timezone"):
        RecoveryBundle.model_validate(naive_timestamp)


class FakeRecoveryClient:
    def __init__(self, *, existing_household: bool = True, owner: bool = True) -> None:
        self.existing_household = existing_household
        self.owner = owner
        self.rpc_calls: list[tuple[str, dict[str, Any] | None]] = []

    async def rpc(self, name: str, payload: dict[str, Any] | None = None) -> Any:
        self.rpc_calls.append((name, payload))
        if name == "get_current_household":
            return HOUSEHOLD_ID if self.existing_household else None
        if name == "export_household_bundle":
            return valid_bundle_payload()
        if name == "restore_household_bundle":
            return {
                "household_id": HOUSEHOLD_ID,
                "restored": True,
                "idempotent_replay": False,
                "summary": valid_bundle().summary(),
            }
        raise AssertionError(f"unexpected RPC: {name}")

    async def request(self, method: str, path: str, **kwargs: Any) -> Any:
        del method, kwargs
        if path != "household_members":
            raise AssertionError(f"unexpected path: {path}")
        return [
            {
                "id": OWNER_ID,
                "profile_id": USER_ID if self.owner else "00000000-0000-0000-0000-000000000099",
                "display_name": "Fictional owner",
                "member_type": "user",
                "role": "owner",
                "is_active": True,
                "created_at": NOW,
            }
        ]


async def test_export_requires_owner_and_validates_rpc_bundle() -> None:
    fake = FakeRecoveryClient()

    result = await export_recovery_bundle(
        cast(SupabaseRestClient, fake), AuthContext(user_id=USER_ID)
    )

    assert RecoveryBundle.model_validate(result).summary() == valid_bundle().summary()
    assert fake.rpc_calls == [
        ("get_current_household", None),
        ("export_household_bundle", None),
    ]

    with pytest.raises(HTTPException) as error:
        await export_recovery_bundle(
            cast(SupabaseRestClient, FakeRecoveryClient(owner=False)),
            AuthContext(user_id=USER_ID),
        )
    assert error.value.status_code == 403


async def test_preview_reports_empty_household_eligibility_and_stable_hash() -> None:
    bundle = valid_bundle()
    eligible = await preview_recovery_bundle(
        bundle,
        cast(SupabaseRestClient, FakeRecoveryClient(existing_household=False)),
    )
    blocked = await preview_recovery_bundle(
        bundle,
        cast(SupabaseRestClient, FakeRecoveryClient(existing_household=True)),
    )

    assert eligible["eligible"] is True
    assert eligible["blocker"] is None
    assert eligible["sha256"] == bundle.summary()["sha256"]
    assert eligible["transactions"] == 4
    assert blocked["eligible"] is False
    assert blocked["blocker"] == "Restore requires a new account with no existing household."


async def test_restore_passes_validated_json_idempotency_and_checksum() -> None:
    fake = FakeRecoveryClient(existing_household=False)
    bundle = valid_bundle()

    result = await restore_recovery_bundle(
        bundle,
        cast(SupabaseRestClient, fake),
        "fictional-restore-key",
    )

    name, payload = fake.rpc_calls[-1]
    assert name == "restore_household_bundle"
    assert payload is not None
    assert payload["p_idempotency_key"] == "fictional-restore-key"
    assert payload["p_bundle"]["format"] == "artha-recovery"
    assert payload["p_bundle"]["schema_version"] == 1
    assert result["restored"] is True
    assert result["sha256"] == bundle.summary()["sha256"]
