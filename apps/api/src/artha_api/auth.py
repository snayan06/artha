from __future__ import annotations

import re
from asyncio import Lock
from collections.abc import Mapping
from dataclasses import dataclass
from os import getenv
from time import monotonic
from typing import Annotated, Any, Protocol
from uuid import UUID

import httpx
import jwt
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

bearer_scheme = HTTPBearer(auto_error=False)
ALLOWED_ALGORITHMS = frozenset({"RS256", "ES256"})
DEFAULT_JWKS_TTL_SECONDS = 300
MAX_JWKS_TTL_SECONDS = 3600


class JwtConfigurationError(ValueError):
    pass


class JwtVerificationError(ValueError):
    pass


class JwksUnavailableError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class SupabaseJwtSettings:
    supabase_url: str
    audience: str

    @classmethod
    def from_env(cls) -> SupabaseJwtSettings:
        supabase_url = (getenv("SUPABASE_URL") or "").strip().rstrip("/")
        audience = (getenv("SUPABASE_JWT_AUDIENCE") or "").strip()
        if not supabase_url:
            raise JwtConfigurationError("SUPABASE_URL is required for production authentication")
        if not audience:
            raise JwtConfigurationError(
                "SUPABASE_JWT_AUDIENCE is required for production authentication"
            )
        if not supabase_url.startswith(("https://", "http://")):
            raise JwtConfigurationError("SUPABASE_URL must be an HTTP(S) URL")
        return cls(supabase_url=supabase_url, audience=audience)

    @property
    def issuer(self) -> str:
        return f"{self.supabase_url}/auth/v1"

    @property
    def jwks_url(self) -> str:
        return f"{self.issuer}/.well-known/jwks.json"


@dataclass(frozen=True, slots=True)
class AuthContext:
    user_id: str


class JwtVerifier(Protocol):
    async def verify(self, token: str) -> AuthContext: ...


def _cache_ttl(headers: httpx.Headers) -> int:
    cache_control = headers.get("cache-control", "")
    match = re.search(r"(?:^|,)\s*max-age=(\d+)", cache_control, re.IGNORECASE)
    if match is None:
        return DEFAULT_JWKS_TTL_SECONDS
    return min(int(match.group(1)), MAX_JWKS_TTL_SECONDS)


class SupabaseJwtVerifier:
    def __init__(
        self,
        settings: SupabaseJwtSettings,
        *,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self.settings = settings
        self._client = client or httpx.AsyncClient(timeout=httpx.Timeout(5.0))
        self._owns_client = client is None
        self._keys: dict[str, jwt.PyJWK] = {}
        self._expires_at = 0.0
        self._refresh_lock = Lock()

    async def aclose(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    async def _refresh_keys(self) -> None:
        try:
            response = await self._client.get(self.settings.jwks_url)
            response.raise_for_status()
            payload: Any = response.json()
        except (httpx.HTTPError, ValueError) as error:
            raise JwksUnavailableError("Supabase JWKS is unavailable") from error
        if not isinstance(payload, Mapping) or not isinstance(payload.get("keys"), list):
            raise JwksUnavailableError("Supabase JWKS response is invalid")

        keys: dict[str, jwt.PyJWK] = {}
        for raw_key in payload["keys"]:
            if not isinstance(raw_key, dict):
                continue
            key_id = raw_key.get("kid")
            algorithm = raw_key.get("alg")
            if (
                not isinstance(key_id, str)
                or not key_id
                or algorithm not in ALLOWED_ALGORITHMS
            ):
                continue
            try:
                keys[key_id] = jwt.PyJWK.from_dict(raw_key)
            except (jwt.PyJWTError, ValueError):
                continue
        if not keys:
            raise JwksUnavailableError("Supabase JWKS contains no supported signing keys")
        self._keys = keys
        self._expires_at = monotonic() + _cache_ttl(response.headers)

    async def _signing_key(self, key_id: str) -> jwt.PyJWK:
        cached = self._keys.get(key_id)
        if cached is not None and monotonic() < self._expires_at:
            return cached
        async with self._refresh_lock:
            cached = self._keys.get(key_id)
            if cached is not None and monotonic() < self._expires_at:
                return cached
            await self._refresh_keys()
            selected = self._keys.get(key_id)
            if selected is None:
                raise JwtVerificationError("JWT signing key is not recognized")
            return selected

    async def verify(self, token: str) -> AuthContext:
        try:
            header = jwt.get_unverified_header(token)
        except jwt.PyJWTError as error:
            raise JwtVerificationError("Bearer token is not a valid JWT") from error
        key_id = header.get("kid")
        algorithm = header.get("alg")
        if not isinstance(key_id, str) or not key_id:
            raise JwtVerificationError("JWT key ID is missing")
        if not isinstance(algorithm, str) or algorithm not in ALLOWED_ALGORITHMS:
            raise JwtVerificationError("JWT signing algorithm is not allowed")

        signing_key = await self._signing_key(key_id)
        if signing_key.algorithm_name != algorithm:
            raise JwtVerificationError("JWT signing algorithm does not match its key")
        try:
            claims = jwt.decode(
                token,
                signing_key.key,
                algorithms=[algorithm],
                audience=self.settings.audience,
                issuer=self.settings.issuer,
                options={"require": ["exp", "iss", "aud", "sub"]},
            )
        except jwt.PyJWTError as error:
            raise JwtVerificationError("JWT signature or claims are invalid") from error

        if claims.get("role") == "service_role":
            raise JwtVerificationError("service-role JWTs are not accepted")
        subject = claims.get("sub")
        if not isinstance(subject, str):
            raise JwtVerificationError("JWT subject must be a UUID")
        try:
            user_id = UUID(subject)
        except ValueError as error:
            raise JwtVerificationError("JWT subject must be a UUID") from error
        if str(user_id) != subject.casefold():
            raise JwtVerificationError("JWT subject must be a canonical UUID")
        return AuthContext(user_id=str(user_id))


def _unauthorized(detail: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=detail,
        headers={"WWW-Authenticate": "Bearer"},
    )


async def get_auth_context(
    request: Request,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
) -> AuthContext:
    if not request.app.state.is_production:
        return AuthContext(user_id=request.app.state.demo_user_id)
    if credentials is None or credentials.scheme.casefold() != "bearer":
        raise _unauthorized("Bearer JWT required")

    verifier: JwtVerifier | None = getattr(
        request.app.state, "supabase_jwt_verifier", None
    )
    if verifier is None:
        initialization_lock: Lock | None = getattr(
            request.app.state, "supabase_jwt_initialization_lock", None
        )
        if initialization_lock is None:
            initialization_lock = Lock()
            request.app.state.supabase_jwt_initialization_lock = initialization_lock
        async with initialization_lock:
            verifier = getattr(request.app.state, "supabase_jwt_verifier", None)
            if verifier is None:
                try:
                    verifier = SupabaseJwtVerifier(SupabaseJwtSettings.from_env())
                except JwtConfigurationError as error:
                    raise HTTPException(
                        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                        detail=str(error),
                    ) from error
                request.app.state.supabase_jwt_verifier = verifier
    try:
        context = await verifier.verify(credentials.credentials)
        request.state.supabase_access_token = credentials.credentials
        return context
    except JwtVerificationError as error:
        raise _unauthorized(str(error)) from error
    except JwksUnavailableError as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(error),
        ) from error


AuthDependency = Annotated[AuthContext, Depends(get_auth_context)]
