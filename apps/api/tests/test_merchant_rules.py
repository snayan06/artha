from __future__ import annotations

from typing import Any

from fastapi import FastAPI
from httpx import AsyncClient

from artha_api.models import MerchantMatchType, MerchantRule


def account_id(data: dict[str, Any], name: str) -> int:
    return next(account["id"] for account in data["accounts"] if account["name"] == name)


async def test_learning_normalizes_and_updates_prospective_rule(
    client: AsyncClient, bootstrapped: dict[str, Any]
) -> None:
    hdfc_id = account_id(bootstrapped, "HDFC UPI")
    learned = await client.post(
        "/api/v1/merchant-rules/learn",
        json={
            "match_type": "contains",
            "merchant_pattern": "  STARBUCKS   Coffee ",
            "category": "Coffee",
            "account_id": hdfc_id,
            "priority": 100,
        },
    )
    relearned = await client.post(
        "/api/v1/merchant-rules/learn",
        json={
            "match_type": "contains",
            "merchant_pattern": "starbucks coffee",
            "category": "Food & Dining",
            "account_id": hdfc_id,
            "priority": 250,
        },
    )
    listed = await client.get("/api/v1/merchant-rules")

    assert learned.status_code == 200
    assert learned.json()["merchant_pattern"] == "starbucks coffee"
    assert relearned.json()["id"] == learned.json()["id"]
    assert relearned.json()["category"] == "Food & Dining"
    assert relearned.json()["priority"] == 250
    assert len(listed.json()) == 1


async def test_highest_priority_rule_applies_before_heuristic(
    client: AsyncClient, bootstrapped: dict[str, Any]
) -> None:
    broad = await client.post(
        "/api/v1/merchant-rules",
        json={
            "match_type": "contains",
            "merchant_pattern": "grocer",
            "category": "Household",
            "priority": 200,
        },
    )
    exact = await client.post(
        "/api/v1/merchant-rules",
        json={
            "match_type": "exact",
            "merchant_pattern": "groceries",
            "category": "Essentials",
            "priority": 100,
        },
    )

    first_parse = await client.post(
        "/api/v1/drafts/parse",
        json={"text": "Paid 500 for groceries from HDFC UPI"},
    )
    promoted = await client.patch(
        f"/api/v1/merchant-rules/{exact.json()['id']}", json={"priority": 300}
    )
    second_parse = await client.post(
        "/api/v1/drafts/parse",
        json={"text": "Paid 500 for groceries from HDFC UPI"},
    )

    assert broad.status_code == 201
    assert first_parse.json()["draft"]["category"] == "Household"
    assert first_parse.json()["matched_merchant_rule_id"] == broad.json()["id"]
    assert first_parse.json()["category_source"] == "merchant_rule"
    assert promoted.status_code == 200
    assert second_parse.json()["draft"]["category"] == "Essentials"
    assert second_parse.json()["matched_merchant_rule_id"] == exact.json()["id"]


async def test_account_scope_ownership_and_matching(
    client: AsyncClient, bootstrapped: dict[str, Any]
) -> None:
    hdfc_id = account_id(bootstrapped, "HDFC UPI")
    scoped = await client.post(
        "/api/v1/merchant-rules",
        json={
            "merchant_pattern": "netflix",
            "category": "Subscriptions",
            "account_id": hdfc_id,
            "priority": 100,
        },
    )
    global_rule = await client.post(
        "/api/v1/merchant-rules",
        json={
            "merchant_pattern": "netflix",
            "category": "Entertainment",
            "priority": 100,
        },
    )
    hdfc_parse = await client.post(
        "/api/v1/drafts/parse", json={"text": "Paid 500 for Netflix from HDFC UPI"}
    )
    cash_parse = await client.post(
        "/api/v1/drafts/parse", json={"text": "Paid 500 for Netflix from Cash"}
    )
    unknown_account = await client.post(
        "/api/v1/merchant-rules",
        json={
            "merchant_pattern": "invalid",
            "category": "Invalid",
            "account_id": 999_999,
        },
    )

    assert scoped.status_code == 201
    assert global_rule.status_code == 201
    assert hdfc_parse.json()["draft"]["category"] == "Subscriptions"
    assert cash_parse.json()["draft"]["category"] == "Entertainment"
    assert unknown_account.status_code == 404


async def test_rules_are_user_isolated(
    client: AsyncClient, app: FastAPI, bootstrapped: dict[str, Any]
) -> None:
    async with app.state.session_factory() as session:
        session.add(
            MerchantRule(
                user_id="another-user",
                match_type=MerchantMatchType.EXACT,
                merchant_pattern="groceries",
                category="Private Category",
                priority=10_000,
                active=True,
            )
        )
        await session.commit()

    listed = await client.get("/api/v1/merchant-rules")
    parsed = await client.post(
        "/api/v1/drafts/parse",
        json={"text": "Paid 500 for groceries from HDFC UPI"},
    )

    assert listed.json() == []
    assert parsed.json()["draft"]["category"] == "Groceries"
    assert parsed.json()["category_source"] == "heuristic"
    assert parsed.json()["matched_merchant_rule_id"] is None


async def test_learning_does_not_mutate_historical_transactions(
    client: AsyncClient, bootstrapped: dict[str, Any]
) -> None:
    before = await client.get("/api/v1/transactions")
    historical = next(
        item for item in before.json() if item["description"] == "Groceries"
    )

    learned = await client.post(
        "/api/v1/merchant-rules/learn",
        json={
            "match_type": "exact",
            "merchant_pattern": "groceries",
            "category": "Household Essentials",
            "priority": 500,
        },
    )
    after = await client.get("/api/v1/transactions")
    parsed = await client.post(
        "/api/v1/drafts/parse",
        json={"text": "Paid 500 for groceries from HDFC UPI"},
    )

    unchanged = next(item for item in after.json() if item["id"] == historical["id"])
    assert learned.status_code == 200
    assert historical["category"] == "Groceries"
    assert unchanged["category"] == "Groceries"
    assert parsed.json()["draft"]["category"] == "Household Essentials"


async def test_rule_crud_and_regex_rejection(client: AsyncClient) -> None:
    created = await client.post(
        "/api/v1/merchant-rules",
        json={"merchant_pattern": "uber", "category": "Transport"},
    )
    deactivated = await client.patch(
        f"/api/v1/merchant-rules/{created.json()['id']}", json={"active": False}
    )
    duplicate = await client.post(
        "/api/v1/merchant-rules",
        json={"merchant_pattern": " UBER ", "category": "Travel"},
    )
    rejected_regex = await client.post(
        "/api/v1/merchant-rules",
        json={
            "match_type": "regex",
            "merchant_pattern": "uber.*",
            "category": "Transport",
        },
    )
    deleted = await client.delete(f"/api/v1/merchant-rules/{created.json()['id']}")

    assert created.status_code == 201
    assert deactivated.json()["active"] is False
    assert duplicate.status_code == 409
    assert rejected_regex.status_code == 422
    assert deleted.json() == {"id": created.json()["id"], "deleted": True}
    assert (await client.get("/api/v1/merchant-rules")).json() == []
