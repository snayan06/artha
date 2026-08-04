from __future__ import annotations

from collections.abc import AsyncIterator
from pathlib import Path

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from artha_api.app import create_app


@pytest.fixture
def app(tmp_path: Path) -> FastAPI:
    return create_app(f"sqlite+aiosqlite:///{tmp_path / 'test.db'}")


@pytest.fixture
async def client(app: FastAPI) -> AsyncIterator[AsyncClient]:
    async with app.router.lifespan_context(app):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as http_client:
            yield http_client


@pytest.fixture
async def bootstrapped(client: AsyncClient) -> dict[str, object]:
    response = await client.post("/api/v1/demo/bootstrap")
    assert response.status_code == 201
    return response.json()
