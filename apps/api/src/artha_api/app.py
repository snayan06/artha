from __future__ import annotations

from asyncio import Lock
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from os import getenv

import httpx
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.ext.asyncio import async_sessionmaker

from .assistant_routes import router as assistant_router
from .database import build_engine, create_schema, default_database_url
from .production_routes import router as production_router
from .routes import router
from .security import SecurityHeadersMiddleware
from .supabase_rest import SupabaseRestSettings


def resolve_database_url(database_url: str | None = None) -> str:
    environment = getenv("ARTHA_ENV", "development").casefold()
    if environment == "production":
        raise RuntimeError("production mode uses Supabase REST/RPC, not the demo database")
    configured_url = database_url or getenv("ARTHA_DATABASE_URL")
    return configured_url or default_database_url()


def create_app(database_url: str | None = None) -> FastAPI:
    environment = getenv("ARTHA_ENV", "development").casefold()
    is_production = environment == "production"
    engine = None if is_production else build_engine(resolve_database_url(database_url))
    cors_origins = [
        origin.strip()
        for origin in getenv(
            "ARTHA_CORS_ORIGINS",
            "http://localhost:5173,http://127.0.0.1:5173",
        ).split(",")
        if origin.strip()
    ]

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        if is_production:
            app.state.supabase_rest_settings = SupabaseRestSettings.from_env()
            app.state.supabase_http_client = httpx.AsyncClient(timeout=httpx.Timeout(10.0))
            yield
            verifier = getattr(app.state, "supabase_jwt_verifier", None)
            if verifier is not None:
                await verifier.aclose()
            await app.state.supabase_http_client.aclose()
        else:
            assert engine is not None
            await create_schema(engine)
            app.state.session_factory = async_sessionmaker(engine, expire_on_commit=False)
            yield
            await engine.dispose()

    app = FastAPI(
        title="Artha API",
        version="1.0.0",
        description="Private V1 ledger API. All amounts are integer paise.",
        lifespan=lifespan,
    )
    app.state.is_production = is_production
    app.state.demo_user_id = getenv("ARTHA_DEMO_USER_ID", "demo-user")
    app.state.demo_bootstrap_lock = Lock()
    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_middleware(SecurityHeadersMiddleware, production=is_production)
    if is_production:
        app.include_router(production_router)
    else:
        app.include_router(router)
        app.include_router(assistant_router)
    return app


app = create_app()
