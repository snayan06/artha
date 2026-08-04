"""Run destructive-only-to-fixtures live Supabase household-isolation checks.

Required environment variables are intentionally not loaded from repository files:
ARTHA_SUPABASE_URL, ARTHA_SUPABASE_ANON_KEY, ARTHA_SUPABASE_SERVICE_KEY,
ARTHA_DATABASE_HOST, ARTHA_DATABASE_USER, and ARTHA_DB_PASSWORD.
"""

from __future__ import annotations

import asyncio
import os
import secrets
import uuid

import asyncpg
import httpx
from artha_api.app import create_app
from httpx import ASGITransport

BASE_URL = os.environ["ARTHA_SUPABASE_URL"].rstrip("/")
ANON_KEY = os.environ["ARTHA_SUPABASE_ANON_KEY"]
SERVICE_KEY = os.environ["ARTHA_SUPABASE_SERVICE_KEY"]
created_user_ids: list[str] = []


async def create_user(client: httpx.AsyncClient, label: str) -> str:
    email = f"artha-rls-{label}-{uuid.uuid4().hex}@example.com"
    password = secrets.token_urlsafe(32)
    response = await client.post(
        f"{BASE_URL}/auth/v1/admin/users",
        headers={"apikey": SERVICE_KEY, "Authorization": f"Bearer {SERVICE_KEY}"},
        json={"email": email, "password": password, "email_confirm": True},
    )
    response.raise_for_status()
    created_user_ids.append(response.json()["id"])
    token = await client.post(
        f"{BASE_URL}/auth/v1/token",
        params={"grant_type": "password"},
        headers={"apikey": ANON_KEY},
        json={"email": email, "password": password},
    )
    token.raise_for_status()
    return str(token.json()["access_token"])


async def rest(
    client: httpx.AsyncClient,
    token: str,
    method: str,
    path: str,
    *,
    payload: object | None = None,
    params: dict[str, str] | None = None,
) -> object:
    response = await client.request(
        method,
        f"{BASE_URL}/rest/v1/{path}",
        headers={
            "apikey": ANON_KEY,
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
        json=payload,
        params=params,
    )
    response.raise_for_status()
    return response.json() if response.content else None


async def cleanup() -> None:
    connection = await asyncpg.connect(
        host=os.environ["ARTHA_DATABASE_HOST"],
        port=5432,
        user=os.environ["ARTHA_DATABASE_USER"],
        password=os.environ["ARTHA_DB_PASSWORD"],
        database="postgres",
        ssl="require",
        timeout=20,
    )
    try:
        async with connection.transaction():
            await connection.execute(
                "alter table public.household_members "
                "disable trigger household_members_preserve_active_owner"
            )
            if created_user_ids:
                await connection.execute(
                    "delete from public.households where created_by = any($1::uuid[])",
                    created_user_ids,
                )
                await connection.execute(
                    "delete from auth.users where id = any($1::uuid[])",
                    created_user_ids,
                )
            await connection.execute(
                "alter table public.household_members "
                "enable trigger household_members_preserve_active_owner"
            )
    finally:
        await connection.close()


async def main() -> None:
    async with httpx.AsyncClient(timeout=20) as client:
        try:
            token_a = await create_user(client, "a")
            token_b = await create_user(client, "b")
            api_app = create_app()
            async with (
                api_app.router.lifespan_context(api_app),
                httpx.AsyncClient(
                    transport=ASGITransport(app=api_app), base_url="http://artha.test"
                ) as api_client,
            ):
                    authorization = {"Authorization": f"Bearer {token_a}"}
                    setup_response = await api_client.post(
                        "/api/v1/onboarding/setup",
                        headers=authorization,
                        json={
                            "display_name": "Test A",
                            "household_name": "RLS Household A",
                            "members": [{"name": "Member A"}],
                            "accounts": [
                                {
                                    "name": "Test Bank A",
                                    "kind": "bank",
                                    "opening_balance_paise": 100_000,
                                    "credit_limit_paise": None,
                                    "statement_day": None,
                                    "payment_due_day": None,
                                }
                            ],
                        },
                    )
                    setup_response.raise_for_status()
                    assert len(setup_response.json()["accounts"]) == 1
                    dashboard_response = await api_client.get(
                        "/api/v1/dashboard", headers=authorization
                    )
                    dashboard_response.raise_for_status()
                    assert dashboard_response.json()["total_balance_paise"] == 100_000
            household_a = await rest(client, token_a, "POST", "rpc/get_current_household")
            setup_b = await rest(
                client,
                token_b,
                "POST",
                "rpc/setup_household",
                payload={
                    "p_display_name": "Test B",
                    "p_household_name": "RLS Household B",
                    "p_members": [{"name": "Member B"}],
                    "p_accounts": [
                        {
                            "name": "Test Bank B",
                            "account_type": "bank",
                            "currency": "INR",
                            "opening_balance_paise": 200_000,
                        }
                    ],
                },
            )
            assert isinstance(household_a, str) and isinstance(setup_b, dict)
            household_b = str(setup_b["household_id"])
            visible_a = await rest(client, token_a, "GET", "households", params={"select": "id"})
            visible_b = await rest(client, token_b, "GET", "households", params={"select": "id"})
            cross_a = await rest(
                client,
                token_a,
                "GET",
                "households",
                params={"id": f"eq.{household_b}", "select": "id"},
            )
            cross_b = await rest(
                client,
                token_b,
                "GET",
                "households",
                params={"id": f"eq.{household_a}", "select": "id"},
            )
            assert isinstance(visible_a, list) and {row["id"] for row in visible_a} == {
                household_a
            }
            assert isinstance(visible_b, list) and {row["id"] for row in visible_b} == {
                household_b
            }
            assert cross_a == [] and cross_b == []
            anonymous = await client.get(
                f"{BASE_URL}/rest/v1/accounts",
                headers={"apikey": ANON_KEY},
                params={"select": "id"},
            )
            assert anonymous.status_code in {401, 403} or anonymous.json() == []
            print(
                "live-production-ok api_jwt=1 api_repository=1 users=2 households=2 "
                "cross_household_rows=0 anon_rows=0"
            )
        finally:
            await cleanup()
            print("fictional-test-data-cleaned")


if __name__ == "__main__":
    asyncio.run(main())
