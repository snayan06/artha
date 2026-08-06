# Artha — Overall System Architecture and Deployment Plan

Status: V1 implemented; personal-account deployment pending
Date: 4 August 2026

## Architecture decision

Build Artha as an installable React PWA, styled with Tailwind CSS, backed by a Python FastAPI service and Supabase Postgres. Keep transaction capture deterministic and confirmation-based. Ship the agent behind a separate read-only, provider-independent boundary so the ledger remains usable when AI is unavailable.

This is the complete product architecture: user interface, API, authentication, database, agent, hosting, security and deployment. Python is only the backend and agent layer; it does not replace the React user interface.

## Chosen stack

| Layer | Choice | Decision reason |
|---|---|---|
| Web application | React + TypeScript + Vite PWA | App screens, state, routing, forms, offline drafts and installation |
| Styling and UI system | Tailwind CSS + repository UI components | Layout, colours, spacing and accessible reusable controls |
| Charts | Recharts | Controlled dashboard and agent-generated charts |
| API | Python 3.13, FastAPI, Pydantic v2, Uvicorn | Typed contracts, async APIs, automatic OpenAPI docs |
| Assistant | Strict Pydantic schemas with a model-provider adapter | Typed tool schemas and structured output without coupling the ledger to a provider |
| Auth | Supabase Auth magic link | Simple private pilot authentication |
| Database | Supabase Postgres with RLS | Relational integrity, atomic split accounting and household isolation |
| Migrations | Supabase CLI SQL migrations | Keeps policies, functions and schema versioned together |
| Frontend hosting | Vercel Hobby | Static Vite PWA under the same personal provider as the API |
| Python hosting | Vercel Python runtime | FastAPI function without Render's minute-long idle wake-up |
| AI inference | Gemini 3.5 Flash-Lite via the official SDK; Groq and local Qwen alternatives | Strong structured extraction, provider portability, private local option, no required AI dependency |
| Files | Supabase Storage Free | Receipt images later, protected by household policy |
| CI | GitHub Actions Free | Lint, types, tests and migration checks |

## Runtime shape

```text
React PWA
   │ Supabase access token
   ▼
FastAPI API
   ├── capture parser → transaction draft → user confirmation
   ├── ledger service → atomic Postgres RPC functions
   ├── read models → dashboard, charts, shared balance
   └── assistant → approved read-only tools → validated UI schema
                          │
                 provider adapter
                  ├── Gemini 3.5 Flash-Lite
                  ├── Groq
                  └── Ollama / Qwen3 4B
                         │
                         ▼
              Supabase Postgres + RLS
```

The browser signs in through Supabase and sends its short-lived access token to FastAPI. FastAPI verifies the token and performs normal queries with the user's authorization context so database RLS remains effective. A service-role key is not used in user request paths.

## API boundaries

### V1 endpoints

- `POST /api/v1/drafts/parse`: turn natural language into an unsaved `TransactionDraft`.
- `POST /api/v1/transactions/confirm`: confirm and atomically save a reviewed draft.
- `GET /api/v1/dashboard`: balances, monthly totals, category mix and spend trend.
- `GET /api/v1/transactions`: searchable and filterable ledger.
- `PATCH /api/v1/transactions/{id}`: audited correction with balance recalculation.
- `DELETE /api/v1/transactions/{id}`: soft delete only.
- `GET /api/v1/shared-balances`: calculated balances for every household member.

Settlement and complete user-owned export endpoints remain launch-gate work and
must not be represented as complete production APIs.

Every write accepts an idempotency key. Amounts are integer paise. Shared expense creation, edit and settlement run in database transactions.

### Capture pipeline

1. A local parser extracts amount, debit/credit language, date, known account and common split phrases.
2. Merchant rules fill learned category/account defaults.
3. Only unresolved fields go to the model fallback, constrained to the household's existing categories.
4. Pydantic validates the returned draft and marks uncertain fields.
5. The user reviews and confirms; parsing never writes to the ledger.

This keeps common entries fast and makes the app usable when the free AI quota is unavailable.

## Assistant and generative UI

Use one analytics assistant, not a multi-agent system. Introduce a workflow engine only if later investment workflows require durable, branching approvals.

Approved agent tools:

- `get_spending_summary(date_range, group_by)`
- `compare_periods(current_range, previous_range, category?)`
- `get_account_balances(as_of?)`
- `get_member_balances(member_ids?)`
- `list_matching_transactions(filters, limit)`
- `evaluate_spending_room(amount, date_range, savings_buffer)`

The tools call predefined read-only database functions. The agent cannot receive a write tool, execute SQL, change a date range silently, or calculate money from prose.

The model returns a validated discriminated union such as:

```json
{
  "answer": "August spending is 8% lower than July.",
  "components": [
    {"type": "metric_card", "label": "August spend", "value_paise": 4268000},
    {"type": "bar_chart", "title": "Top categories", "series": []},
    {"type": "transaction_table", "transaction_ids": []}
  ],
  "evidence": {"date_range": "2026-08-01/2026-08-31", "transaction_count": 37}
}
```

The React app maps these types to reviewed components: `MetricCard`, `LineChart`, `BarChart`, `DonutChart`, `TransactionTable` and `InsightBanner`. It never executes model-generated HTML, JavaScript or SQL.

## Security rules

- RLS is enabled on every exposed table and checks household/user membership.
- User JWTs are verified by FastAPI; service-role credentials stay out of user-facing routes.
- Agent tools receive the authenticated user and household from server context, never from model arguments.
- All agent answers include a date range, transaction count and linkable source IDs.
- Raw account/card numbers are never stored; account names are user-defined labels.
- Model-bound text is minimized and identifiers are replaced where possible.
- Audit events record transaction edits, deletes, settlements and agent tool calls.
- Rate limits, request-size limits and strict CORS apply at the API.

## ₹0 deployment choice

### Pilot deployment

- PWA: Vercel Hobby project rooted at `apps/web` on a `vercel.app` URL.
- API: separate Vercel Hobby project rooted at `apps/api` on a `vercel.app` URL.
- Auth/database/storage: Supabase Free.
- AI: Gemini's free developer tier for fictional evaluation, with Groq, local Ollama and manual fallbacks.
- Source/CI: public GitHub repository and GitHub Actions.

This is genuinely usable at ₹0 for the user's private pilot. The limitations are explicit:

- Vercel Hobby is restricted to personal non-commercial use and its Python runtime is beta.
- Vercel functions have usage, duration and bundle-size limits; the API must fail explicitly when unavailable.
- Supabase can pause a free project after one inactive week and does not include managed backups.
- Free hosted AI capacity is capped and provider policies can change; capture still works through rules and manual review.
- Free-tier Gemini data terms are not appropriate for real family finance; use a paid privacy configuration or keep hosted AI disabled.
- A custom domain and WhatsApp Business messaging are not included in the ₹0 promise.

The checked-in Render blueprint remains a container fallback, but its free service
spins down after 15 idle minutes and can take about a minute to wake. Google Cloud
Run is another later option, but it requires billing setup and can charge beyond
quota, so neither is the strict no-billing default.

Current official references: [Vercel Hobby](https://vercel.com/docs/plans/hobby), [Vercel FastAPI](https://vercel.com/docs/frameworks/backend/fastapi), [Vercel monorepos](https://vercel.com/docs/monorepos), [Supabase pricing](https://supabase.com/pricing), [Supabase RLS](https://supabase.com/docs/guides/database/postgres/row-level-security), [Render Free fallback](https://render.com/docs/free), [Groq rate limits](https://console.groq.com/docs/rate-limits), [Qwen3.6-27B model card](https://huggingface.co/Qwen/Qwen3.6-27B), and [Ollama structured output](https://docs.ollama.com/capabilities/structured-outputs).

## Repository shape

```text
artha/
  apps/
    web/                 # React PWA
    api/                 # FastAPI application
  packages/
    contracts/           # generated TypeScript API types
  supabase/
    migrations/          # schema, RLS, RPC functions
    seed.sql
  docs/
    architecture/
  .github/workflows/
```

## Build sequence

1. Week 1: repo, auth, RLS, accounts, opening balances and ledger invariants.
2. Week 2: parse/review/confirm capture, dashboard charts and offline draft queue.
3. Week 3: multi-member shared calculations, corrections, settlements and CSV export.
4. Week 4: mobile QA, security tests, Vercel/Supabase deployment and private use.
5. V2: read-only agent tools, inline UI schema, evaluation set and source-linked answers.

The first implementation milestone is not the chatbot. It is a ledger whose balances, transfers, credit cards and shared splits remain correct under edits and retries.
