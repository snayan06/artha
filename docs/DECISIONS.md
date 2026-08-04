# Architecture decisions

## ADR-001: PWA before messaging integrations

The React PWA is the source of truth. WhatsApp and Telegram may later submit drafts through the same API, but neither owns the ledger.

## ADR-002: Python API boundary

FastAPI owns validation, parsing orchestration and business services. Production data is stored in Supabase Postgres with RLS. Local demo mode uses SQLite so development and tests do not require cloud credentials.

## ADR-003: confirmation before financial writes

Natural language produces a `TransactionDraft`. Only the confirmation endpoint may create ledger entries. The parser and future agent cannot write directly.

## ADR-004: derived balances

Account balances, spending and shared receivables are derived from immutable-style ledger facts. Corrections are audited and deletes are soft.

## ADR-005: constrained V2 agent

The V2 agent receives only predefined read-only analytics tools. It cannot execute SQL or render arbitrary code. Its structured output maps to reviewed React components.

## ADR-006: experimental Qwen default and deferred model benchmark

The private pilot uses `qwen/qwen3.6-27b` through Groq as its experimental
hosted model because it supports text, images, reasoning, tool use and structured
JSON through one provider. Deterministic parsing and merchant rules still run
first, and the model cannot write transactions or calculate ledger totals.

A representative Artha evaluation and comparison against other hosted models is
required before a production model is locked. That evaluation is backlog work
and does not block the V1 private pilot.

## ADR-007: Vercel Hobby and Supabase Free for the private pilot

Deploy the public monorepo as two Vercel projects owned by the user's personal
account: `apps/web` for the Vite PWA and `apps/api` for the FastAPI function.
Use a fresh Supabase Free project under the same personal ownership for Auth,
Postgres and RLS.

This replaces Cloudflare Pages plus Render as the default because it removes one
provider and avoids Render Free's approximately one-minute wake-up after idle,
which conflicts with five-second capture. Render remains a documented container
fallback through `render.yaml`.

The trade-offs are explicit: Vercel's Python runtime is beta, Hobby is for
personal non-commercial use and has usage caps; Supabase Free can pause after
low activity and has no managed backups. Artha therefore fails closed at API
errors and requires encrypted export/restore before real financial data.
