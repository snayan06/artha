.PHONY: setup dev-web dev-api test lint build check check-sql check-supabase-link check-live-rpc-catalog eval-capture-validate eval-capture-hosted

setup:
	npm --prefix apps/web ci
	cd apps/api && uv sync --locked --all-groups

dev-web:
	npm --prefix apps/web run dev -- --host 127.0.0.1

dev-api:
	cd apps/api && uv run uvicorn artha_api.app:app --reload --port 8000 --env-file ../../.env

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

check: lint test build check-sql
	python scripts/check_capture_evals.py
	$(MAKE) eval-capture-validate

check-sql:
	uv run --with 'pglast>=7,<8' python scripts/check_sql.py

check-supabase-link:
	@test -n "$$ARTHA_SUPABASE_PROJECT_REF" || (echo "ARTHA_SUPABASE_PROJECT_REF is required" >&2; exit 1)
	@test -f supabase/.temp/project-ref || (echo "Supabase is not linked; refusing a production database command" >&2; exit 1)
	@test "$$(cat supabase/.temp/project-ref)" = "$$ARTHA_SUPABASE_PROJECT_REF" || (echo "Supabase link does not match ARTHA_SUPABASE_PROJECT_REF; refusing a production database command" >&2; exit 1)

check-live-rpc-catalog:
	python scripts/check_live_rpc_catalog.py

eval-capture-validate:
	cd apps/api && uv run python -m artha_api.capture_evals --mode validate

eval-capture-hosted:
	cd apps/api && uv run python -m artha_api.capture_evals --mode run
