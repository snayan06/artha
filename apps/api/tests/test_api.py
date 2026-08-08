from __future__ import annotations

import asyncio
from typing import Any

from fastapi import FastAPI
from httpx import AsyncClient

from artha_api.models import Account


def account_id(data: dict[str, Any], name: str) -> int:
    return next(account["id"] for account in data["accounts"] if account["name"] == name)


def member_id(data: dict[str, Any], name: str = "Avery") -> int:
    return next(member["id"] for member in data["members"] if member["name"] == name)


async def test_health_and_idempotent_demo_bootstrap(client: AsyncClient) -> None:
    health = await client.get("/health")
    assert health.status_code == 200
    assert health.json() == {"status": "ok", "version": "v1"}

    first = await client.post("/api/v1/demo/bootstrap")
    second = await client.post("/api/v1/demo/bootstrap")

    assert first.status_code == 201
    assert first.json()["created"] is True
    assert second.status_code == 200
    assert second.json()["created"] is False
    assert len(second.json()["accounts"]) == 2
    assert len(second.json()["transactions"]) == 2


async def test_concurrent_demo_bootstrap_is_replay_safe(client: AsyncClient) -> None:
    first, second = await asyncio.gather(
        client.post("/api/v1/demo/bootstrap"),
        client.post("/api/v1/demo/bootstrap"),
    )

    assert sorted([first.status_code, second.status_code]) == [200, 201]
    assert sorted([first.json()["created"], second.json()["created"]]) == [False, True]
    assert len(first.json()["accounts"]) == len(second.json()["accounts"]) == 2
    assert len(first.json()["transactions"]) == len(second.json()["transactions"]) == 2


async def test_capture_context_is_owner_scoped_and_filters_archived_accounts(
    app: FastAPI,
    client: AsyncClient,
) -> None:
    async with app.state.session_factory() as session:
        session.add_all(
            [
                Account(user_id="demo-user", name="Active bank", kind="bank"),
                Account(
                    user_id="demo-user",
                    name="Archived bank",
                    kind="bank",
                    is_archived=True,
                ),
                Account(user_id="another-owner", name="Other bank", kind="bank"),
            ]
        )
        await session.commit()

    response = await client.get("/api/v1/capture-context")

    assert response.status_code == 200
    assert [account["name"] for account in response.json()["accounts"]] == [
        "Active bank"
    ]
    assert response.json()["categories"]
    assert {category["kind"] for category in response.json()["categories"]} == {
        "expense",
        "income",
        "both",
    }


async def test_seed_dashboard_respects_personal_share_and_account_movement(
    client: AsyncClient, bootstrapped: dict[str, Any]
) -> None:
    response = await client.get("/api/v1/dashboard")
    dashboard = response.json()

    assert response.status_code == 200
    assert dashboard["total_balance_paise"] == 1_441_000
    assert dashboard["spend_paise"] == 92_000
    assert dashboard["income_paise"] == 350_000
    assert dashboard["net_cashflow_paise"] == 166_000
    assert dashboard["member_balances"][0]["balance_paise"] == 92_000
    assert dashboard["spend_by_category"] == [
        {"category": "Groceries", "amount_paise": 92_000}
    ]
    assert len(dashboard["monthly"]) == 6
    assert dashboard["monthly"][-1]["income_paise"] == 350_000
    assert dashboard["monthly"][-1]["spend_paise"] == 92_000


async def test_parser_handles_reference_quick_add(
    client: AsyncClient, bootstrapped: dict[str, Any]
) -> None:
    response = await client.post(
        "/api/v1/drafts/parse",
        json={"text": "Paid 1840 for groceries from HDFC UPI, split equally with Avery"},
    )
    body = response.json()

    assert response.status_code == 200
    assert body["confidence"] == 0.97
    assert body["warnings"] == []
    assert body["draft"] == {
        "kind": "expense",
        "amount_paise": 184_000,
        "description": "Groceries",
        "category": "Groceries",
        "paid_by_member_id": None,
        "settlement_member_id": None,
        "personal_share_paise": 92_000,
        "splits": [{"member_id": member_id(bootstrapped), "amount_paise": 92_000}],
        "source_account_id": account_id(bootstrapped, "HDFC UPI"),
        "destination_account_id": None,
        "settlement_direction": None,
        "occurred_at": None,
        "notes": (
            "Parsed from: Paid 1840 for groceries from HDFC UPI, "
            "split equally with Avery"
        ),
    }


async def test_parser_supports_decimal_amount_and_safe_fallback_account(
    client: AsyncClient, bootstrapped: dict[str, Any]
) -> None:
    response = await client.post(
        "/api/v1/drafts/parse", json={"text": "Spent Rs. 1,234.56 for shopping"}
    )
    body = response.json()

    assert response.status_code == 200
    assert body["draft"]["amount_paise"] == 123_456
    assert body["draft"]["category"] == "Shopping"
    assert body["draft"]["source_account_id"] == account_id(bootstrapped, "HDFC UPI")
    assert body["warnings"] == ["Account was not explicit; using HDFC UPI."]


async def test_parser_rejects_invalid_iana_timezone(
    client: AsyncClient, bootstrapped: dict[str, Any]
) -> None:
    response = await client.post(
        "/api/v1/drafts/parse",
        json={
            "text": "Paid 500 for groceries from HDFC UPI today",
            "timezone": "Mars/Olympus_Mons",
        },
    )

    assert response.status_code == 422
    assert response.json()["detail"] == "timezone must be a valid IANA timezone"


async def test_confirm_is_idempotent_and_rejects_key_reuse(
    client: AsyncClient, bootstrapped: dict[str, Any]
) -> None:
    parsed = await client.post(
        "/api/v1/drafts/parse",
        json={"text": "Paid 1840 for groceries from HDFC UPI, split equally with Avery"},
    )
    draft = parsed.json()["draft"]
    headers = {"Idempotency-Key": "quick-add-0001"}

    first = await client.post("/api/v1/transactions/confirm", json=draft, headers=headers)
    replay = await client.post("/api/v1/transactions/confirm", json=draft, headers=headers)
    changed = {**draft, "description": "Different"}
    conflict = await client.post("/api/v1/transactions/confirm", json=changed, headers=headers)

    assert first.status_code == 201
    assert replay.status_code == 201
    assert first.json()["id"] == replay.json()["id"]
    assert first.json()["account_delta_paise"] == -184_000
    assert first.json()["member_balance_deltas"] == [
        {"member_id": member_id(bootstrapped), "amount_paise": 92_000}
    ]
    assert conflict.status_code == 409
    transactions = await client.get("/api/v1/transactions")
    assert len(transactions.json()) == 3


async def test_confirm_requires_an_exact_grounded_category(
    client: AsyncClient, bootstrapped: dict[str, Any]
) -> None:
    account = account_id(bootstrapped, "HDFC UPI")
    base = {
        "kind": "expense",
        "amount_paise": 1_000,
        "description": "Crafted category",
        "personal_share_paise": 1_000,
        "splits": [],
        "source_account_id": account,
    }

    invented = await client.post(
        "/api/v1/transactions/confirm",
        json={**base, "category": "Invented"},
        headers={"Idempotency-Key": "category-invented"},
    )
    wildcard = await client.post(
        "/api/v1/transactions/confirm",
        json={**base, "category": "Gro%"},
        headers={"Idempotency-Key": "category-wildcard"},
    )
    wrong_direction = await client.post(
        "/api/v1/transactions/confirm",
        json={**base, "category": "Salary"},
        headers={"Idempotency-Key": "category-direction"},
    )
    valid = await client.post(
        "/api/v1/transactions/confirm",
        json={**base, "category": "  gRoCeRiEs  "},
        headers={"Idempotency-Key": "category-normalized"},
    )

    assert invented.status_code == 422
    assert wildcard.status_code == 422
    assert wrong_direction.status_code == 422
    assert valid.status_code == 201
    assert valid.json()["category"] == "Groceries"


async def test_transfer_changes_accounts_but_not_spend_or_total(
    client: AsyncClient, bootstrapped: dict[str, Any]
) -> None:
    before = (await client.get("/api/v1/dashboard")).json()
    response = await client.post(
        "/api/v1/transactions/confirm",
        headers={"Idempotency-Key": "transfer-0001"},
        json={
            "kind": "transfer",
            "amount_paise": 10_000,
            "description": "ATM withdrawal",
            "category": "Crafted unsafe transfer category",
            "paid_by_member_id": None,
            "settlement_member_id": None,
            "personal_share_paise": 10_000,
            "splits": [],
            "source_account_id": account_id(bootstrapped, "HDFC UPI"),
            "destination_account_id": account_id(bootstrapped, "Cash"),
        },
    )
    after = (await client.get("/api/v1/dashboard")).json()

    assert response.status_code == 201
    assert response.json()["category"] == "Transfer"
    assert response.json()["account_delta_paise"] == 0
    assert after["total_balance_paise"] == before["total_balance_paise"]
    assert after["spend_paise"] == before["spend_paise"]
    assert after["net_cashflow_paise"] == before["net_cashflow_paise"]


async def test_credit_card_payment_reduces_cash_and_outstanding_without_new_spend(
    client: AsyncClient, bootstrapped: dict[str, Any]
) -> None:
    card = await client.post(
        "/api/v1/accounts",
        json={
            "name": "Travel Card",
            "kind": "credit_card",
            "opening_balance_paise": -50_000,
            "credit_limit_paise": 500_000,
        },
    )
    card_id = card.json()["id"]
    bank_id = account_id(bootstrapped, "HDFC UPI")
    before_dashboard = (await client.get("/api/v1/dashboard")).json()
    before_accounts = {
        account["id"]: account for account in (await client.get("/api/v1/accounts")).json()
    }

    payment = await client.post(
        "/api/v1/transactions/confirm",
        headers={"Idempotency-Key": "card-payment-0001"},
        json={
            "kind": "transfer",
            "amount_paise": 20_000,
            "description": "Credit card payment",
            "category": None,
            "paid_by_member_id": None,
            "settlement_member_id": None,
            "personal_share_paise": 20_000,
            "splits": [],
            "source_account_id": bank_id,
            "destination_account_id": card_id,
        },
    )
    after_dashboard = (await client.get("/api/v1/dashboard")).json()
    after_accounts = {
        account["id"]: account for account in (await client.get("/api/v1/accounts")).json()
    }

    assert payment.status_code == 201
    assert payment.json()["account_delta_paise"] == 0
    assert after_accounts[bank_id]["current_balance_paise"] == (
        before_accounts[bank_id]["current_balance_paise"] - 20_000
    )
    assert after_accounts[card_id]["current_balance_paise"] == -30_000
    assert after_dashboard["total_balance_paise"] == before_dashboard["total_balance_paise"]
    assert after_dashboard["spend_paise"] == before_dashboard["spend_paise"]
    assert after_dashboard["income_paise"] == before_dashboard["income_paise"]


async def test_settlement_is_cash_movement_not_income_or_spend(
    client: AsyncClient, bootstrapped: dict[str, Any]
) -> None:
    before = (await client.get("/api/v1/dashboard")).json()
    response = await client.post(
        "/api/v1/transactions/confirm",
        headers={"Idempotency-Key": "settlement-0001"},
        json={
            "kind": "settlement",
            "amount_paise": 20_000,
            "description": "Avery paid back",
            "category": None,
            "paid_by_member_id": None,
            "settlement_member_id": member_id(bootstrapped),
            "personal_share_paise": 20_000,
            "splits": [],
            "source_account_id": account_id(bootstrapped, "HDFC UPI"),
            "settlement_direction": "received",
        },
    )
    after = (await client.get("/api/v1/dashboard")).json()

    assert response.status_code == 201
    assert response.json()["account_delta_paise"] == 20_000
    assert response.json()["member_balance_deltas"] == [
        {"member_id": member_id(bootstrapped), "amount_paise": -20_000}
    ]
    assert after["total_balance_paise"] == before["total_balance_paise"] + 20_000
    assert after["spend_paise"] == before["spend_paise"]
    assert after["income_paise"] == before["income_paise"]
    assert after["member_balances"][0]["balance_paise"] == (
        before["member_balances"][0]["balance_paise"] - 20_000
    )
    shared = (await client.get("/api/v1/shared-balances")).json()
    assert shared["balances"][0]["member_name"] == "Avery"
    assert shared["balances"][0]["status"] == "Avery owes you"


async def test_member_paid_expense_has_no_user_account_movement(
    client: AsyncClient, bootstrapped: dict[str, Any]
) -> None:
    before = (await client.get("/api/v1/dashboard")).json()
    response = await client.post(
        "/api/v1/transactions/confirm",
        headers={"Idempotency-Key": "member-paid-0001"},
        json={
            "kind": "expense",
            "amount_paise": 50_000,
            "description": "Dinner",
            "category": "Food & Dining",
            "paid_by_member_id": member_id(bootstrapped),
            "settlement_member_id": None,
            "personal_share_paise": 25_000,
            "splits": [
                {"member_id": member_id(bootstrapped), "amount_paise": 25_000}
            ],
            "source_account_id": account_id(bootstrapped, "HDFC UPI"),
        },
    )
    after = (await client.get("/api/v1/dashboard")).json()

    assert response.status_code == 201
    assert response.json()["account_delta_paise"] == 0
    assert response.json()["member_balance_deltas"] == [
        {"member_id": member_id(bootstrapped), "amount_paise": -25_000}
    ]
    assert after["total_balance_paise"] == before["total_balance_paise"]
    assert after["spend_paise"] == before["spend_paise"] + 25_000


async def test_user_paid_settlement_clears_payable_without_new_spending(
    client: AsyncClient, bootstrapped: dict[str, Any]
) -> None:
    member = member_id(bootstrapped)
    account = account_id(bootstrapped, "HDFC UPI")
    member_paid = await client.post(
        "/api/v1/transactions/confirm",
        headers={"Idempotency-Key": "member-paid-before-settlement-0001"},
        json={
            "kind": "expense",
            "amount_paise": 50_000,
            "description": "Member paid dinner",
            "category": "Food & Dining",
            "paid_by_member_id": member,
            "settlement_member_id": None,
            "personal_share_paise": 25_000,
            "splits": [{"member_id": member, "amount_paise": 25_000}],
            "source_account_id": account,
        },
    )
    before_settlement = (await client.get("/api/v1/dashboard")).json()
    settlement = await client.post(
        "/api/v1/transactions/confirm",
        headers={"Idempotency-Key": "paid-settlement-0001"},
        json={
            "kind": "settlement",
            "amount_paise": 25_000,
            "description": "Paid Avery back",
            "category": None,
            "paid_by_member_id": None,
            "settlement_member_id": member,
            "personal_share_paise": 25_000,
            "splits": [],
            "source_account_id": account,
            "settlement_direction": "paid",
        },
    )
    after_settlement = (await client.get("/api/v1/dashboard")).json()

    assert member_paid.status_code == 201
    assert settlement.status_code == 201
    assert settlement.json()["account_delta_paise"] == -25_000
    assert settlement.json()["member_balance_deltas"] == [
        {"member_id": member, "amount_paise": 25_000}
    ]
    assert after_settlement["member_balances"][0]["balance_paise"] == 92_000
    assert after_settlement["spend_paise"] == before_settlement["spend_paise"]
    assert after_settlement["income_paise"] == before_settlement["income_paise"]


async def test_edit_rebuilds_ledger_and_soft_delete_removes_effects(
    client: AsyncClient, bootstrapped: dict[str, Any]
) -> None:
    parsed = await client.post(
        "/api/v1/drafts/parse",
        json={"text": "Paid 1840 for groceries from HDFC UPI, split equally with Avery"},
    )
    confirmed = await client.post(
        "/api/v1/transactions/confirm",
        json=parsed.json()["draft"],
        headers={"Idempotency-Key": "edit-delete-0001"},
    )
    transaction_id = confirmed.json()["id"]
    before_edit = (await client.get("/api/v1/dashboard")).json()

    edited = await client.patch(
        f"/api/v1/transactions/{transaction_id}",
        json={
            "amount_paise": 100_000,
            "personal_share_paise": 50_000,
            "splits": [
                {"member_id": member_id(bootstrapped), "amount_paise": 50_000}
            ],
        },
    )
    after_edit = (await client.get("/api/v1/dashboard")).json()
    deleted = await client.delete(f"/api/v1/transactions/{transaction_id}")
    after_delete = (await client.get("/api/v1/dashboard")).json()

    assert edited.status_code == 200
    assert edited.json()["account_delta_paise"] == -100_000
    assert edited.json()["member_balance_deltas"] == [
        {"member_id": member_id(bootstrapped), "amount_paise": 50_000}
    ]
    assert after_edit["total_balance_paise"] == before_edit["total_balance_paise"] + 84_000
    assert deleted.json() == {"id": transaction_id, "deleted": True}
    assert after_delete["total_balance_paise"] == 1_441_000
    assert after_delete["member_balances"][0]["balance_paise"] == 92_000
    listed_ids = {item["id"] for item in (await client.get("/api/v1/transactions")).json()}
    assert transaction_id not in listed_ids


async def test_account_creation_opening_balance_and_validation(client: AsyncClient) -> None:
    account = await client.post(
        "/api/v1/accounts",
        json={"name": "Travel Wallet", "kind": "wallet", "opening_balance_paise": 12_345},
    )
    duplicate = await client.post(
        "/api/v1/accounts",
        json={"name": "Travel Wallet", "kind": "wallet", "opening_balance_paise": 0},
    )
    updated = await client.patch(
        f"/api/v1/accounts/{account.json()['id']}/opening-balance",
        json={"opening_balance_paise": 20_000},
    )

    assert account.status_code == 201
    assert account.json()["current_balance_paise"] == 12_345
    assert duplicate.status_code == 409
    assert updated.json()["current_balance_paise"] == 20_000


async def test_atomic_account_setup_supports_credit_cards(client: AsyncClient) -> None:
    response = await client.post(
        "/api/v1/accounts/setup",
        json={
            "accounts": [
                {
                    "name": "Primary Bank",
                    "kind": "bank",
                    "opening_balance_paise": 500_000,
                },
                {
                    "name": "Travel Card",
                    "kind": "credit_card",
                    "opening_balance_paise": -125_000,
                    "credit_limit_paise": 1_000_000,
                    "statement_day": 12,
                    "payment_due_day": 30,
                },
            ]
        },
    )

    assert response.status_code == 201
    assert [account["name"] for account in response.json()] == ["Primary Bank", "Travel Card"]
    credit_card = response.json()[1]
    assert credit_card["current_balance_paise"] == -125_000
    assert credit_card["credit_limit_paise"] == 1_000_000
    assert credit_card["statement_day"] == 12
    assert credit_card["payment_due_day"] == 30


async def test_onboarding_supports_four_money_accounts_and_multiple_cards(
    client: AsyncClient,
) -> None:
    response = await client.post(
        "/api/v1/onboarding/setup",
        json={
            "accounts": [
                {"name": "Salary Bank", "kind": "bank", "opening_balance_paise": 100_000},
                {"name": "Savings Bank", "kind": "bank", "opening_balance_paise": 200_000},
                {"name": "UPI Bank", "kind": "bank", "opening_balance_paise": 300_000},
                {"name": "Cash", "kind": "cash", "opening_balance_paise": 10_000},
                {
                    "name": "Travel Card",
                    "kind": "credit_card",
                    "opening_balance_paise": -20_000,
                    "credit_limit_paise": 500_000,
                },
                {
                    "name": "Rewards Card",
                    "kind": "credit_card",
                    "opening_balance_paise": -30_000,
                    "credit_limit_paise": 750_000,
                },
            ],
            "members": [{"name": "Avery"}, {"name": "Jordan"}],
        },
    )

    assert response.status_code == 201
    assert len(response.json()["accounts"]) == 6
    assert len(response.json()["members"]) == 2
    assert sum(
        account["current_balance_paise"] for account in response.json()["accounts"]
    ) == 560_000


async def test_account_setup_rejects_duplicates_atomically(client: AsyncClient) -> None:
    within_request = await client.post(
        "/api/v1/accounts/setup",
        json={
            "accounts": [
                {"name": "Savings", "kind": "bank", "opening_balance_paise": 100},
                {"name": " savings ", "kind": "cash", "opening_balance_paise": 200},
            ]
        },
    )
    after_request_duplicate = await client.get("/api/v1/accounts")

    existing = await client.post(
        "/api/v1/accounts",
        json={"name": "Existing", "kind": "bank", "opening_balance_paise": 300},
    )
    existing_duplicate = await client.post(
        "/api/v1/accounts/setup",
        json={
            "accounts": [
                {"name": "New Account", "kind": "cash", "opening_balance_paise": 400},
                {"name": "EXISTING", "kind": "wallet", "opening_balance_paise": 500},
            ]
        },
    )
    after_existing_duplicate = await client.get("/api/v1/accounts")

    assert within_request.status_code == 409
    assert after_request_duplicate.json() == []
    assert existing.status_code == 201
    assert existing_duplicate.status_code == 409
    assert [account["name"] for account in after_existing_duplicate.json()] == ["Existing"]


async def test_credit_card_fields_are_validated(client: AsyncClient) -> None:
    credit_limit_on_bank = await client.post(
        "/api/v1/accounts",
        json={
            "name": "Invalid Bank",
            "kind": "bank",
            "opening_balance_paise": 0,
            "credit_limit_paise": 100_000,
        },
    )
    positive_outstanding = await client.post(
        "/api/v1/accounts",
        json={
            "name": "Invalid Card Balance",
            "kind": "credit_card",
            "opening_balance_paise": 50_000,
        },
    )
    invalid_statement_day = await client.post(
        "/api/v1/accounts",
        json={
            "name": "Invalid Statement Day",
            "kind": "credit_card",
            "opening_balance_paise": -50_000,
            "statement_day": 32,
        },
    )
    outstanding_above_limit = await client.post(
        "/api/v1/accounts",
        json={
            "name": "Over Limit Card",
            "kind": "credit_card",
            "opening_balance_paise": -200_000,
            "credit_limit_paise": 100_000,
        },
    )
    too_many_accounts = await client.post(
        "/api/v1/accounts/setup",
        json={
            "accounts": [
                {"name": f"Account {index}", "kind": "cash", "opening_balance_paise": 0}
                for index in range(21)
            ]
        },
    )
    valid_card = await client.post(
        "/api/v1/accounts",
        json={
            "name": "Valid Card",
            "kind": "credit_card",
            "opening_balance_paise": -10_000,
        },
    )
    invalid_balance_update = await client.patch(
        f"/api/v1/accounts/{valid_card.json()['id']}/opening-balance",
        json={"opening_balance_paise": 10_000},
    )

    assert credit_limit_on_bank.status_code == 422
    assert positive_outstanding.status_code == 422
    assert invalid_statement_day.status_code == 422
    assert outstanding_above_limit.status_code == 422
    assert too_many_accounts.status_code == 422
    assert invalid_balance_update.status_code == 422


async def test_onboarding_and_multi_member_balances(client: AsyncClient) -> None:
    onboarding = await client.post(
        "/api/v1/onboarding/setup",
        json={
            "accounts": [
                {"name": "Family Bank", "kind": "bank", "opening_balance_paise": 50_000}
            ],
            "members": [{"name": "Maya"}, {"name": "Leo"}],
        },
    )
    assert onboarding.status_code == 201
    family_account_id = onboarding.json()["accounts"][0]["id"]
    maya_id = onboarding.json()["members"][0]["id"]
    leo_id = onboarding.json()["members"][1]["id"]

    user_paid = await client.post(
        "/api/v1/transactions/confirm",
        headers={"Idempotency-Key": "multi-user-paid-0001"},
        json={
            "kind": "expense",
            "amount_paise": 1_000,
            "description": "Household supplies",
            "category": "Other",
            "paid_by_member_id": None,
            "settlement_member_id": None,
            "personal_share_paise": 400,
            "splits": [
                {"member_id": maya_id, "amount_paise": 300},
                {"member_id": leo_id, "amount_paise": 300},
            ],
            "source_account_id": family_account_id,
        },
    )
    member_paid = await client.post(
        "/api/v1/transactions/confirm",
        headers={"Idempotency-Key": "multi-member-paid-0001"},
        json={
            "kind": "expense",
            "amount_paise": 1_000,
            "description": "Dinner",
            "category": "Food & Dining",
            "paid_by_member_id": leo_id,
            "settlement_member_id": None,
            "personal_share_paise": 500,
            "splits": [{"member_id": maya_id, "amount_paise": 500}],
            "source_account_id": family_account_id,
        },
    )
    balances = await client.get("/api/v1/shared-balances")

    assert user_paid.status_code == 201
    assert user_paid.json()["member_balance_deltas"] == [
        {"member_id": maya_id, "amount_paise": 300},
        {"member_id": leo_id, "amount_paise": 300},
    ]
    assert member_paid.status_code == 201
    assert member_paid.json()["account_delta_paise"] == 0
    assert member_paid.json()["member_balance_deltas"] == [
        {"member_id": leo_id, "amount_paise": -500}
    ]
    assert {
        item["member_name"]: item["balance_paise"] for item in balances.json()["balances"]
    } == {"Maya": 300, "Leo": -200}


async def test_onboarding_rejects_member_duplicates_atomically(client: AsyncClient) -> None:
    response = await client.post(
        "/api/v1/onboarding/setup",
        json={
            "accounts": [
                {"name": "Should Roll Back", "kind": "cash", "opening_balance_paise": 100}
            ],
            "members": [{"name": "Sam"}, {"name": " sam "}],
        },
    )

    assert response.status_code == 409
    assert (await client.get("/api/v1/accounts")).json() == []
    assert (await client.get("/api/v1/members")).json() == []


async def test_parser_builds_multi_member_split(client: AsyncClient) -> None:
    onboarding = await client.post(
        "/api/v1/onboarding/setup",
        json={
            "accounts": [
                {"name": "Family Bank", "kind": "bank", "opening_balance_paise": 0}
            ],
            "members": [{"name": "Maya"}, {"name": "Leo"}],
        },
    )
    members = onboarding.json()["members"]
    response = await client.post(
        "/api/v1/drafts/parse",
        json={
            "text": (
                "Paid 900 for dinner from Family Bank, split equally with Maya and Leo "
                "3 days ago"
            ),
            "timezone": "Asia/Kolkata",
        },
    )

    assert response.status_code == 200
    draft = response.json()["draft"]
    assert draft["personal_share_paise"] == 30_000
    assert draft["splits"] == [
        {"member_id": members[0]["id"], "amount_paise": 30_000},
        {"member_id": members[1]["id"], "amount_paise": 30_000},
    ]
    assert draft["occurred_at"] is not None


async def test_invalid_share_sum_and_same_account_transfer_are_rejected(
    client: AsyncClient, bootstrapped: dict[str, Any]
) -> None:
    account = account_id(bootstrapped, "HDFC UPI")
    bad_split = await client.post(
        "/api/v1/transactions/confirm",
        headers={"Idempotency-Key": "bad-split-0001"},
        json={
            "kind": "expense",
            "amount_paise": 1_000,
            "description": "Bad split",
            "paid_by_member_id": None,
            "settlement_member_id": None,
            "personal_share_paise": 500,
            "splits": [{"member_id": member_id(bootstrapped), "amount_paise": 400}],
            "source_account_id": account,
        },
    )
    bad_transfer = await client.post(
        "/api/v1/transactions/confirm",
        headers={"Idempotency-Key": "bad-transfer-0001"},
        json={
            "kind": "transfer",
            "amount_paise": 1_000,
            "description": "Bad transfer",
            "paid_by_member_id": None,
            "settlement_member_id": None,
            "personal_share_paise": 1_000,
            "splits": [],
            "source_account_id": account,
            "destination_account_id": account,
        },
    )

    assert bad_split.status_code == 422
    assert bad_transfer.status_code == 422


async def test_duplicate_splits_and_unknown_ledger_references_are_rejected(
    client: AsyncClient, bootstrapped: dict[str, Any]
) -> None:
    account = account_id(bootstrapped, "HDFC UPI")
    member = member_id(bootstrapped)
    duplicate_splits = await client.post(
        "/api/v1/transactions/confirm",
        headers={"Idempotency-Key": "duplicate-splits-0001"},
        json={
            "kind": "expense",
            "amount_paise": 1_000,
            "description": "Duplicate split",
            "category": "Other",
            "personal_share_paise": 400,
            "splits": [
                {"member_id": member, "amount_paise": 300},
                {"member_id": member, "amount_paise": 300},
            ],
            "source_account_id": account,
        },
    )
    unknown_account = await client.post(
        "/api/v1/transactions/confirm",
        headers={"Idempotency-Key": "unknown-account-0001"},
        json={
            "kind": "expense",
            "amount_paise": 1_000,
            "description": "Unknown account",
            "category": "Other",
            "personal_share_paise": 1_000,
            "splits": [],
            "source_account_id": 999_999,
        },
    )
    unknown_member = await client.post(
        "/api/v1/transactions/confirm",
        headers={"Idempotency-Key": "unknown-member-0001"},
        json={
            "kind": "expense",
            "amount_paise": 1_000,
            "description": "Unknown member",
            "category": "Other",
            "personal_share_paise": 500,
            "splits": [{"member_id": 999_999, "amount_paise": 500}],
            "source_account_id": account,
        },
    )

    assert duplicate_splits.status_code == 422
    assert unknown_account.status_code == 404
    assert unknown_account.json()["detail"] == "account not found or archived"
    assert unknown_member.status_code == 404
    assert unknown_member.json()["detail"] == "household member not found or archived"


async def test_concurrent_same_key_confirmation_never_duplicates_the_ledger(
    client: AsyncClient, bootstrapped: dict[str, Any]
) -> None:
    parsed = await client.post(
        "/api/v1/drafts/parse",
        json={"text": "Paid 250 for lunch from HDFC UPI"},
    )
    draft = parsed.json()["draft"]
    headers = {"Idempotency-Key": "concurrent-confirm-0001"}

    first, second = await asyncio.gather(
        client.post("/api/v1/transactions/confirm", json=draft, headers=headers),
        client.post("/api/v1/transactions/confirm", json=draft, headers=headers),
    )
    transactions = (await client.get("/api/v1/transactions")).json()
    matching = [item for item in transactions if item["description"] == "Lunch"]

    assert 201 in {first.status_code, second.status_code}
    assert {first.status_code, second.status_code}.issubset({201, 409})
    assert len(matching) == 1
