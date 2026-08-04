from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import BigInteger, insert, select

from artha_api.app import create_app, resolve_database_url
from artha_api.models import (
    Account,
    HouseholdMember,
    LedgerEntry,
    Transaction,
    TransactionKind,
    TransactionSplit,
)


@asynccontextmanager
async def app_client(database_path: Path) -> AsyncIterator[tuple[AsyncClient, FastAPI]]:
    app = create_app(f"sqlite+aiosqlite:///{database_path}")
    async with app.router.lifespan_context(app):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            yield client, app


def test_production_storage_never_uses_demo_database(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ARTHA_ENV", "production")
    monkeypatch.delenv("ARTHA_DATABASE_URL", raising=False)
    monkeypatch.delenv("ARTHA_ALLOW_DEMO_STORAGE", raising=False)

    with pytest.raises(RuntimeError, match="uses Supabase REST/RPC"):
        resolve_database_url()
    app = create_app()
    assert app.state.is_production is True
    with pytest.raises(RuntimeError, match="uses Supabase REST/RPC"):
        resolve_database_url("sqlite+aiosqlite:///unsafe.db")

    monkeypatch.setenv("ARTHA_ALLOW_DEMO_STORAGE", "true")
    with pytest.raises(RuntimeError, match="uses Supabase REST/RPC"):
        resolve_database_url("sqlite+aiosqlite:///explicit-demo.db")


def test_preview_mode_explicitly_allows_disposable_sqlite(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ARTHA_ENV", "preview")

    assert resolve_database_url("sqlite+aiosqlite:///preview.db").endswith("preview.db")


async def test_demo_user_id_is_environment_driven(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ARTHA_ENV", "development")
    monkeypatch.setenv("ARTHA_DEMO_USER_ID", "local-demo-owner")

    async with app_client(tmp_path / "demo-user.db") as (client, app):
        response = await client.post("/api/v1/demo/bootstrap")
        async with app.state.session_factory() as session:
            stored_user_ids = set((await session.scalars(select(Account.user_id))).all())

    assert response.status_code == 201
    assert stored_user_ids == {"local-demo-owner"}


async def test_money_columns_are_bigint_and_round_trip_large_paise(
    client: AsyncClient,
) -> None:
    money_columns = (
        Account.__table__.c.opening_balance_paise,
        Account.__table__.c.credit_limit_paise,
        Transaction.__table__.c.amount_paise,
        Transaction.__table__.c.personal_share_paise,
        TransactionSplit.__table__.c.amount_paise,
        LedgerEntry.__table__.c.delta_paise,
    )
    assert all(isinstance(column.type, BigInteger) for column in money_columns)

    large_balance = 9_000_000_000_000
    response = await client.post(
        "/api/v1/accounts",
        json={
            "name": "Large Balance Test",
            "kind": "bank",
            "opening_balance_paise": large_balance,
        },
    )

    assert response.status_code == 201
    assert response.json()["opening_balance_paise"] == large_balance
    assert response.json()["current_balance_paise"] == large_balance


async def test_shared_and_dashboard_aggregates_are_not_row_capped(tmp_path: Path) -> None:
    transaction_count = 10_001
    async with app_client(tmp_path / "unbounded-aggregate.db") as (client, app):
        account_response = await client.post(
            "/api/v1/accounts",
            json={"name": "Aggregate Account", "kind": "bank", "opening_balance_paise": 0},
        )
        source_account_id = account_response.json()["id"]
        async with app.state.session_factory() as session:
            member = HouseholdMember(user_id="demo-user", name="Jordan")
            session.add(member)
            await session.commit()
            await session.refresh(member)
        values = [
            {
                "user_id": "demo-user",
                "kind": TransactionKind.EXPENSE,
                "amount_paise": 1,
                "personal_share_paise": 1,
                "description": "Aggregate boundary test",
                "paid_by_member_id": member.id,
                "source_account_id": source_account_id,
            }
            for _ in range(transaction_count)
        ]
        async with app.state.session_factory() as session:
            await session.execute(insert(Transaction), values)
            await session.commit()

        shared = await client.get("/api/v1/shared-balances")
        dashboard = await client.get("/api/v1/dashboard")

    assert shared.status_code == 200
    assert shared.json()["balances"][0]["balance_paise"] == -transaction_count
    assert dashboard.json()["member_balances"][0]["balance_paise"] == -transaction_count
    assert len(dashboard.json()["recent_transactions"]) == 10
