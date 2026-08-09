from __future__ import annotations

from dataclasses import dataclass
from os import getenv
from typing import Any

import httpx
from fastapi import HTTPException, Request, status

from .auth import AuthContext

GENERIC_DATABASE_CONFLICT = "database write conflicts with existing data"
SAFE_DATABASE_CONFLICT_DETAILS = {
    "an active account with this name already exists": (
        "An active account with this name already exists."
    ),
    "idempotency key was already used for a different request": (
        "This request was already used with different details. Please try again."
    ),
}


def safe_database_conflict_detail(response: httpx.Response) -> str:
    try:
        payload = response.json()
    except ValueError:
        return GENERIC_DATABASE_CONFLICT
    if not isinstance(payload, dict):
        return GENERIC_DATABASE_CONFLICT
    message = payload.get("message")
    if not isinstance(message, str):
        return GENERIC_DATABASE_CONFLICT
    normalized = message.strip().casefold().removesuffix(".")
    return SAFE_DATABASE_CONFLICT_DETAILS.get(
        normalized,
        GENERIC_DATABASE_CONFLICT,
    )


@dataclass(frozen=True, slots=True)
class SupabaseRestSettings:
    url: str
    anon_key: str

    @classmethod
    def from_env(cls) -> SupabaseRestSettings:
        url = (getenv("SUPABASE_URL") or "").strip().rstrip("/")
        anon_key = (getenv("SUPABASE_ANON_KEY") or "").strip()
        if not url or not anon_key:
            raise RuntimeError("SUPABASE_URL and SUPABASE_ANON_KEY are required")
        if not url.startswith("https://"):
            raise RuntimeError("production Supabase URL must use HTTPS")
        return cls(url=url, anon_key=anon_key)


class SupabaseRestClient:
    def __init__(
        self,
        http_client: httpx.AsyncClient,
        settings: SupabaseRestSettings,
        access_token: str,
    ) -> None:
        self._client = http_client
        self._base_url = f"{settings.url}/rest/v1"
        self._headers = {
            "apikey": settings.anon_key,
            "Authorization": f"Bearer {access_token}",
            "Accept": "application/json",
            "Content-Type": "application/json",
        }

    async def request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, str] | None = None,
        payload: Any = None,
        prefer: str | None = None,
    ) -> Any:
        headers = dict(self._headers)
        if prefer:
            headers["Prefer"] = prefer
        try:
            response = await self._client.request(
                method,
                f"{self._base_url}/{path.lstrip('/')}",
                params=params,
                json=payload,
                headers=headers,
            )
        except httpx.HTTPError as error:
            raise HTTPException(
                status.HTTP_503_SERVICE_UNAVAILABLE,
                "production database is temporarily unavailable",
            ) from error
        if response.is_success:
            if response.status_code == status.HTTP_204_NO_CONTENT or not response.content:
                return None
            return response.json()
        if response.status_code in {status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN}:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "database access was denied")
        if response.status_code == status.HTTP_404_NOT_FOUND:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "database record was not found")
        if response.status_code == status.HTTP_409_CONFLICT:
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                safe_database_conflict_detail(response),
            )
        if response.status_code in {
            status.HTTP_400_BAD_REQUEST,
            status.HTTP_422_UNPROCESSABLE_CONTENT,
        }:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_CONTENT, "database rejected the request"
            )
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "production database request failed",
        )

    async def rpc(self, name: str, payload: dict[str, Any] | None = None) -> Any:
        return await self.request("POST", f"rpc/{name}", payload=payload or {})


def rest_client_for_request(request: Request, auth: AuthContext) -> SupabaseRestClient:
    del auth
    access_token = getattr(request.state, "supabase_access_token", None)
    if not isinstance(access_token, str) or not access_token:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Bearer JWT required")
    settings: SupabaseRestSettings = request.app.state.supabase_rest_settings
    http_client: httpx.AsyncClient = request.app.state.supabase_http_client
    return SupabaseRestClient(http_client, settings, access_token)
