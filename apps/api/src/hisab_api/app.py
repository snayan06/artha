from __future__ import annotations

from asyncio import Lock
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from os import getenv

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.ext.asyncio import async_sessionmaker

from .assistant_routes import router as assistant_router
from .database import build_engine, create_schema, default_database_url
from .routes import router


def resolve_database_url(database_url: str | None = None) -> str:
    environment = getenv("HISAB_ENV", "development").casefold()
    if environment == "production":
        raise RuntimeError(
            "Production mode is intentionally disabled until Supabase JWT verification "
            "and the Supabase repository adapter are connected and live RLS tests pass"
        )
    configured_url = database_url or getenv("HISAB_DATABASE_URL")
    return configured_url or default_database_url()


def create_app(database_url: str | None = None) -> FastAPI:
    environment = getenv("HISAB_ENV", "development").casefold()
    engine = build_engine(resolve_database_url(database_url))
    cors_origins = [
        origin.strip()
        for origin in getenv(
            "HISAB_CORS_ORIGINS",
            "http://localhost:5173,http://127.0.0.1:5173",
        ).split(",")
        if origin.strip()
    ]

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        await create_schema(engine)
        app.state.session_factory = async_sessionmaker(engine, expire_on_commit=False)
        yield
        await engine.dispose()

    app = FastAPI(
        title="Hisab API",
        version="1.0.0",
        description="Private V1 ledger API. All amounts are integer paise.",
        lifespan=lifespan,
    )
    app.state.is_production = environment == "production"
    app.state.demo_user_id = getenv("HISAB_DEMO_USER_ID", "demo-user")
    app.state.demo_bootstrap_lock = Lock()
    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(router)
    app.include_router(assistant_router)
    return app


app = create_app()
