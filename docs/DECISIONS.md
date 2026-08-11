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

## ADR-006: Gemini is the production model

**Decision date:** 7 August 2026

**Decision:** Use Gemini as the only hosted production LLM. Keep explicit
Ollama selection development-only.

**Rationale:** One hosted path keeps deployment, privacy review and failure
handling explicit. Gemini passed the sanitized sample capture, tagging and assistant
schema gates while preserving Artha's review-before-write boundary.

**Consequences:** Model output remains untrusted and fail-closed. Capture can
create only a validated unsaved draft; category suggestions must match
server-owned authenticated household categories; assistant output must equal an
intent's canonical server-owned bundle. Unavailable or invalid output never
creates a guessed ledger fact or fabricated answer. Production merchant-rule
integration remains planned.

Mutable provider configuration, bounded contexts and failure flows belong in
the [system architecture](system-architecture.md) and
[LLM usage map](artifacts/architecture/v1-llm-usage-map.md), not this decision
record.

## ADR-007: Vercel Hobby and Supabase Free for personal production use

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

## ADR-008: versioned transaction metadata before relational tags

**Decision date:** 9 August 2026

**Decision:** Store only explicitly confirmed, bounded metadata version 1 inside
the existing RLS-protected `transactions.metadata` JSON object for the messaging
release. Defer household-managed tags, aliases, relational links and indexed
merchant/platform analytics to a separately migrated release.

**Rationale:** The existing confirmation RPC already writes the transaction and
metadata atomically, and encrypted recovery already preserves the JSON object.
This ships the inspectable merchant/platform/category/context review without a
new database or recovery format. FastAPI still owns the strict schema, review
status, source allow-list, normalized safe tag names and transfer/income
exclusions.

**Consequences:** Raw capture text is never persisted. Current optional tags are
from a small server-owned explicit-phrase catalog. Cross-transaction tag
management and efficient metadata analytics remain backlog work and must not be
claimed as current product behavior.

## ADR-009: tiered Gemini model strategy for Artha Analyst

**Decision date:** 11 August 2026

**Decision:** Keep `gemini-3.5-flash-lite` as the production default for
capture, auto-tagging, intent routing and the current fixed-intent assistant.
Benchmark `gemini-3.6-flash` as the only initial challenger for the future
bounded multi-tool Artha Analyst. Do not adopt `gemini-3.5-flash`,
`gemini-3.1-flash-lite` or `gemini-3.1-pro-preview` without new evidence.

**Rationale:** Both selected candidates are current stable GA models with
function calling, structured output and thinking support. Google positions 3.5
Flash-Lite for low-cost high-throughput structured execution and 3.6 Flash for
more complex agentic workflows. The existing 3.5 Flash-Lite path has already
passed Artha's capture, tagging, routing and assistant gates. Gemini 3.6 Flash
has the same paid input price as 3.5 Flash and a lower paid output price while
being the newer agentic model, so 3.5 Flash adds no useful first benchmark arm.
The Pro model is preview-only, paid-only and unnecessary for the initial
bounded three-tool analyst. The older 3.1 Flash-Lite is cheaper but would trade
away recency after 3.5 Flash-Lite already met the fast-path gates.

**Privacy consequence:** Google's current pricing page states that free-tier
content is used to improve its products, while paid-tier content is not. Free
tier therefore remains restricted to fictional/demo evaluation. Real personal
finance text stays disabled until Artha has an explicitly approved paid data
configuration in addition to `store=false`; model selection alone does not
approve private-data processing.

**Promotion gate:** The Analyst model is selected from versioned fictional
planner, argument, calculation, evidence, follow-up, scenario, safety, latency,
token and cost evaluations. No model is promoted solely because it is newer or
scores better on a general benchmark. See the
[Artha Analyst plan](artifacts/architecture/2026-08-11-artha-analyst-agent-plan.md).

## ADR-010: Google ADK for the bounded analyst beta

**Decision date:** 11 August 2026

**Decision:** Use Google Agent Development Kit (ADK) for the demo/test-account
Artha Analyst beta. Keep the August 13 production assistant on its existing
direct Gemini path until ADK passes Artha's versioned tool, evidence, safety,
latency and privacy evaluations.

**Rationale:** ADK fits the existing Python, FastAPI and Gemini stack and adds
typed tool orchestration, local trace inspection and agent trajectory
evaluation without adopting a second model ecosystem. LangGraph is stronger
when durable, provider-neutral, long-running graphs are the primary need; that
is not the initial bounded two-turn, three-tool Artha workflow.

**Guardrail:** ADK does not receive ledger-write tools, raw SQL or unrestricted
database access. Framework adoption does not change Artha's human-confirmed
writes or private-data approval requirements.
