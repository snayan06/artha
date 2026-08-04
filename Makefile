.PHONY: setup dev-web dev-api test lint build check

setup:
	npm --prefix apps/web ci
	cd apps/api && uv sync --locked --all-groups

dev-web:
	npm run dev:web

dev-api:
	cd apps/api && uv run uvicorn artha_api.app:app --reload --port 8000

test:
	npm run test:web
	cd apps/api && uv run pytest

lint:
	npm run lint:web
	npm run typecheck:web
	cd apps/api && uv run ruff check .
	cd apps/api && uv run mypy

build:
	npm run build:web

check: lint test build
