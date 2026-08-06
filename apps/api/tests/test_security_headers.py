from __future__ import annotations

from httpx import AsyncClient


async def test_api_responses_are_not_cacheable_and_have_security_headers(
    client: AsyncClient,
) -> None:
    response = await client.post("/api/v1/demo/bootstrap")

    assert response.status_code == 201
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["x-frame-options"] == "DENY"
    assert response.headers["referrer-policy"] == "no-referrer"
    assert response.headers["permissions-policy"] == "camera=(), microphone=(), geolocation=()"


async def test_health_response_has_security_headers_without_forcing_api_cache_policy(
    client: AsyncClient,
) -> None:
    response = await client.get("/health")

    assert response.status_code == 200
    assert "cache-control" not in response.headers
    assert response.headers["x-content-type-options"] == "nosniff"
