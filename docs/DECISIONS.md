# Architecture decisions

## ADR-001: PWA before messaging integrations

The React PWA is the source of truth. WhatsApp and Telegram may later submit drafts through the same API, but neither owns the ledger.

## ADR-002: Python API boundary

FastAPI owns validation, parsing orchestration and business services. Production data is stored in Supabase Postgres with RLS. Local demo mode uses SQLite so development and tests do not require cloud credentials.

## ADR-003: confirmation before financial writes

Natural language produces a `TransactionDraft`. Only the confirmation endpoint may create ledger entries. The parser and future agent cannot write directly.

## ADR-004: derived balances

Account balances, spending and shared receivables are derived from immutable-style ledger facts. Corrections are audited and deletes are soft.

## ADR-005: constrained read-only assistant

The assistant operates on a bounded, server-built financial snapshot. Gemini
selects one supported intent and must copy its exact approved narrative and
canonical widget bundle. FastAPI rejects changed titles, labels, values, rows,
points, order or cardinality before React renders repository-owned components.
The assistant cannot alter the ledger or render arbitrary model code.

## ADR-006: Gemini is the production private-pilot model

**Decision date:** 7 August 2026

The production private pilot uses `gemini-3.5-flash-lite` through Google's
official server-side SDK for natural-language capture, allow-listed category
suggestions and the read-only assistant. One hosted path keeps deployment,
privacy review and failure handling explicit, while strict schemas performed
well across the fictional capture, tagging and assistant gates.

Gemini interpretation never writes the ledger. Capture output must pass schema,
household allow-list, integer-paise and split validation before it becomes an
unsaved review draft; only explicit confirmation writes. If interpretation is
unavailable or invalid, Artha preserves the exact text and opens the manual form
without guessing.

Merchant-rule-first matching and learning remain available in the local
SQLAlchemy demo path. Production Supabase Quick Add and category suggestion call
Gemini directly today; production merchant-rule integration is planned. Gemini
may select only an existing category, and failure leaves the choice to the user.

For the assistant, server code owns the bounded context and exact canonical
bundle for every supported intent. Gemini selects an intent and must copy its
approved narrative and bundle without changing titles, labels, values, rows,
points, order or cardinality. Invalid or unavailable output produces a sanitized
`503`, not a fabricated answer. An explicitly configured Ollama adapter may be
used for local development only and is not part of the production decision.

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
