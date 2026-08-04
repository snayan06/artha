from __future__ import annotations

import json
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID, uuid4

import httpx
import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi import FastAPI, HTTPException
from fastapi.security import HTTPAuthorizationCredentials
from starlette.requests import Request

from artha_api.auth import (
    AuthContext,
    JwksUnavailableError,
    JwtVerificationError,
    SupabaseJwtSettings,
    SupabaseJwtVerifier,
    get_auth_context,
)

ISSUER = "https://project.supabase.co/auth/v1"
AUDIENCE = "authenticated"


def signing_material(key_id: str) -> tuple[rsa.RSAPrivateKey, dict[str, Any]]:
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    jwk = json.loads(jwt.algorithms.RSAAlgorithm.to_jwk(private_key.public_key()))
    jwk.update({"kid": key_id, "alg": "RS256", "use": "sig"})
    return private_key, jwk


def token_for(
    private_key: rsa.RSAPrivateKey,
    key_id: str,
    **overrides: Any,
) -> str:
    now = datetime.now(UTC)
    claims: dict[str, Any] = {
        "iss": ISSUER,
        "aud": AUDIENCE,
        "sub": str(uuid4()),
        "iat": now,
        "exp": now + timedelta(minutes=5),
        "role": "authenticated",
    }
    claims.update(overrides)
    return jwt.encode(claims, private_key, algorithm="RS256", headers={"kid": key_id})


def settings() -> SupabaseJwtSettings:
    return SupabaseJwtSettings(
        supabase_url="https://project.supabase.co",
        audience=AUDIENCE,
    )


async def verifier_with_handler(
    handler: Callable[[httpx.Request], httpx.Response],
) -> tuple[SupabaseJwtVerifier, httpx.AsyncClient]:
    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    return SupabaseJwtVerifier(settings(), client=client), client


async def test_valid_supabase_jwt_uses_exact_jwks_url_and_cache() -> None:
    private_key, public_jwk = signing_material("primary")
    requests: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(str(request.url))
        return httpx.Response(
            200,
            json={"keys": [public_jwk]},
            headers={"Cache-Control": "public, max-age=600"},
        )

    verifier, client = await verifier_with_handler(handler)
    subject = str(uuid4())
    token = token_for(private_key, "primary", sub=subject)
    try:
        first = await verifier.verify(token)
        second = await verifier.verify(token)
    finally:
        await client.aclose()

    assert first == AuthContext(user_id=subject)
    assert second == first
    assert requests == [f"{ISSUER}/.well-known/jwks.json"]


@pytest.mark.parametrize(
    "overrides",
    [
        {"iss": "https://attacker.example/auth/v1"},
        {"aud": "wrong-audience"},
        {"sub": "not-a-uuid"},
        {"role": "service_role"},
        {"exp": datetime.now(UTC) - timedelta(minutes=1)},
    ],
)
async def test_invalid_claims_and_service_role_are_rejected(
    overrides: dict[str, Any],
) -> None:
    private_key, public_jwk = signing_material("primary")

    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"keys": [public_jwk]})

    verifier, client = await verifier_with_handler(handler)
    try:
        with pytest.raises(JwtVerificationError):
            await verifier.verify(token_for(private_key, "primary", **overrides))
    finally:
        await client.aclose()


async def test_disallowed_symmetric_algorithm_is_rejected_without_jwks_fetch() -> None:
    requests = 0

    def handler(_request: httpx.Request) -> httpx.Response:
        nonlocal requests
        requests += 1
        return httpx.Response(500)

    verifier, client = await verifier_with_handler(handler)
    token = jwt.encode(
        {"sub": str(uuid4())},
        "not-a-supabase-secret-but-long-enough",
        algorithm="HS256",
        headers={"kid": "legacy"},
    )
    try:
        with pytest.raises(JwtVerificationError, match="algorithm"):
            await verifier.verify(token)
    finally:
        await client.aclose()
    assert requests == 0


async def test_token_signed_by_untrusted_key_is_rejected() -> None:
    _trusted_private, trusted_jwk = signing_material("primary")
    attacker_private, _attacker_jwk = signing_material("attacker")

    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"keys": [trusted_jwk]})

    verifier, client = await verifier_with_handler(handler)
    forged = token_for(attacker_private, "primary")
    try:
        with pytest.raises(JwtVerificationError, match="signature or claims"):
            await verifier.verify(forged)
    finally:
        await client.aclose()


async def test_unknown_kid_refreshes_jwks_for_key_rotation() -> None:
    private_one, jwk_one = signing_material("one")
    private_two, jwk_two = signing_material("two")
    requests = 0

    def handler(_request: httpx.Request) -> httpx.Response:
        nonlocal requests
        requests += 1
        keys = [jwk_one] if requests == 1 else [jwk_one, jwk_two]
        return httpx.Response(200, json={"keys": keys}, headers={"Cache-Control": "max-age=600"})

    verifier, client = await verifier_with_handler(handler)
    try:
        await verifier.verify(token_for(private_one, "one"))
        rotated = await verifier.verify(token_for(private_two, "two"))
    finally:
        await client.aclose()

    assert UUID(rotated.user_id)
    assert requests == 2


def request_for(app: FastAPI) -> Request:
    return Request({"type": "http", "method": "GET", "path": "/", "headers": [], "app": app})


async def test_demo_auth_remains_unauthenticated() -> None:
    app = FastAPI()
    app.state.is_production = False
    app.state.demo_user_id = "demo-owner"

    context = await get_auth_context(request_for(app), None)

    assert context == AuthContext(user_id="demo-owner")


async def test_production_requires_bearer_and_configuration(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app = FastAPI()
    app.state.is_production = True
    request = request_for(app)

    with pytest.raises(HTTPException) as missing_bearer:
        await get_auth_context(request, None)
    assert missing_bearer.value.status_code == 401
    assert missing_bearer.value.headers == {"WWW-Authenticate": "Bearer"}

    monkeypatch.delenv("SUPABASE_URL", raising=False)
    monkeypatch.delenv("SUPABASE_JWT_AUDIENCE", raising=False)
    credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials="token")
    with pytest.raises(HTTPException) as missing_configuration:
        await get_auth_context(request, credentials)
    assert missing_configuration.value.status_code == 503


async def test_jwks_outage_maps_to_service_unavailable() -> None:
    class UnavailableVerifier:
        async def verify(self, _token: str) -> AuthContext:
            raise JwksUnavailableError("Supabase JWKS is unavailable")

    app = FastAPI()
    app.state.is_production = True
    app.state.supabase_jwt_verifier = UnavailableVerifier()
    credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials="token")

    with pytest.raises(HTTPException) as unavailable:
        await get_auth_context(request_for(app), credentials)

    assert unavailable.value.status_code == 503
    assert unavailable.value.detail == "Supabase JWKS is unavailable"
