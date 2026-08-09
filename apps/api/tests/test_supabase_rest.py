from __future__ import annotations

import httpx
import pytest
from fastapi import HTTPException

from artha_api.supabase_rest import SupabaseRestClient, SupabaseRestSettings


@pytest.mark.parametrize(
    ("database_message", "expected_detail"),
    [
        (
            "an active account with this name already exists",
            "An active account with this name already exists.",
        ),
        (
            "idempotency key was already used for a different request",
            "This request was already used with different details. Please try again.",
        ),
        (
            "another database conflict",
            "database write conflicts with existing data",
        ),
    ],
)
async def test_database_conflicts_expose_only_allow_listed_guidance(
    database_message: str,
    expected_detail: str,
) -> None:
    def conflict_response(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            409,
            request=request,
            json={"code": "23505", "message": database_message},
        )

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(conflict_response)
    ) as http_client:
        client = SupabaseRestClient(
            http_client,
            SupabaseRestSettings(
                url="https://example.supabase.co",
                anon_key="test-anon-key",
            ),
            "test-access-token",
        )

        with pytest.raises(HTTPException) as error:
            await client.rpc("create_managed_account", {"p_name": "Known Bank"})

    assert error.value.status_code == 409
    assert error.value.detail == expected_detail
