# Artha — System architecture and deployment

Status: V1 private pilot deployed; current runtime documented
Date: 7 August 2026

## Architecture decision

Artha is an installable React PWA backed by FastAPI and Supabase Postgres. In
production, Gemini interprets natural-language capture and assistant questions.
Application and database code retain authority over identity, allowed entities,
money, splits and writes.

The key product boundary is review before save. Quick Add creates an unsaved,
strictly validated draft; only explicit confirmation reaches the ledger. If
Gemini is unavailable or cannot return a valid interpretation, Artha preserves
the user's exact text and opens the manual form. Production does not substitute
a language parser or manufacture a likely draft.

## Chosen stack

| Layer | Choice | Responsibility |
|---|---|---|
| Web application | React 19 + TypeScript + Vite PWA | Screens, review/edit state, approved assistant widgets and installation |
| Styling and charts | Tailwind CSS + repository UI components + Recharts | Accessible presentation controlled by application code |
| API | Python 3.13, FastAPI, Pydantic v2, SQLAlchemy async | Authenticated orchestration, schemas, allow-lists and business services |
| Authentication | Supabase Auth magic link | Private-pilot identity and short-lived access tokens |
| Production database | Supabase Postgres with RLS | Ledger truth, relational integrity, atomic RPCs and household isolation |
| Local database | SQLite + aiosqlite | Keyless local demo and development |
| Production AI | Gemini 3.5 Flash-Lite via Google's official SDK | Structured capture interpretation, category suggestions and assistant selection |
| Hosting | Separate Vercel projects for the PWA and FastAPI | Current private-pilot deployment |
| CI | GitHub Actions | Lint, types, tests and migration checks |

An explicit Ollama provider remains available for local development. It is not
part of the production deployment, production evaluation gate or user-facing
recovery path.

## Runtime topology

```text
React PWA / Vercel
   │ Supabase access token
   ▼
FastAPI / Vercel ───── server-side only ─────► Gemini
   │
   ├── capture orchestration ─► validated unsaved draft ─► review ─► confirm
   ├── ledger and read models ─► atomic database functions
   └── assistant contract ─────► approved narrative and widget selection
   │
   ▼
Supabase Postgres / RLS
```

The browser signs in through Supabase and sends its short-lived access token to
FastAPI. FastAPI verifies the token and uses the authenticated database context
so RLS remains effective. Gemini credentials and calls stay server-side. A
service-role key is not used in normal user request paths.

## Quick Add trust flow

1. The authenticated user sends natural text to
   `POST /api/v1/drafts/parse`.
2. FastAPI loads grounded household context: current date/timezone and allowed
   account, member and category identifiers.
3. Gemini interprets the text into the strict capture schema.
4. Application code rejects malformed values, invented IDs, invalid dates,
   floating-point money and inconsistent splits.
5. A valid result becomes an unsaved draft in the review UI. The user may edit
   any field.
6. Only `POST /api/v1/transactions/confirm`, with an idempotency key, can invoke
   the atomic ledger write.

If step 3 or 4 fails, the exact source text is retained and the manual form
opens. No deterministic language-parser guess is promoted as production
recovery, and nothing is saved.

Production Quick Add currently asks Gemini to select from existing household
categories as part of capture; it does not load or apply `merchant_rules`.
The standalone production tag-suggestion endpoint accepts only description,
amount and direction; FastAPI loads up to 200 active, direction-eligible
categories from the authenticated household and supplies that allow-list to
Gemini. The V1 web app does not call this endpoint. The local SQLAlchemy demo
path can match and learn merchant rules before model suggestion. Connecting that
learned rule behavior to Supabase production capture is planned, not a live
production claim.

## Assistant and generative UI

The assistant is read-only and LLM-powered. FastAPI first creates a bounded
financial snapshot from authenticated dashboard context: total balance,
current-month spending and income, up to 20 member balances, 5 top categories,
6 monthly cash-flow points and 8 recent transaction summaries.

From that snapshot, server code builds the exact canonical widget bundle for
each supported intent: `summary`, `spending`, `income`, `cashflow`, `shared`,
`transactions`, `clarification` and `unsupported`. Gemini selects one intent and
must copy that intent's approved narrative and widget array exactly. FastAPI
rejects any changed title, label, value, row, point, order or cardinality; React
then renders repository-owned metric, chart, table or clarification components.

Gemini cannot calculate authoritative financial values, add arbitrary numeric
prose, alter the ledger or render HTML/JavaScript. When Gemini is unavailable or
its output is invalid, the API returns a sanitized `503` and the UI shows an
honest error; it does not fall back to fabricated cards or an assistant answer.

## Ledger and security rules

- Money is integer paise throughout the contract and database.
- Transfers and card payments are account movements, not new spending.
- Shared cash movement and personal expense share remain separate.
- Every financial write is explicit, validated, idempotent and atomic.
- RLS is enabled on exposed household tables.
- Account, member and category references are resolved against authenticated
  household allow-lists.
- Model output is untrusted input; arbitrary model HTML or JavaScript is never
  rendered.
- Raw account/card numbers are neither required nor stored.
- Free-tier Gemini must receive fictional data only; real financial text needs
  an appropriate paid privacy configuration.

## API boundaries

Important V1 routes include:

- `POST /api/v1/drafts/parse`: interpret natural language into an unsaved draft,
  or return manual-recovery context without guessing.
- `POST /api/v1/transactions/confirm`: atomically save a reviewed draft.
- `GET /api/v1/dashboard`: return server-derived balances and chart data.
- `GET /api/v1/transactions`: return searchable logical ledger activity.
- `PATCH/DELETE /api/v1/transactions/{id}`: audited correction or soft delete.
- `GET /api/v1/shared-balances`: calculate participant receivables/payables.
- `POST /api/v1/assistant/chat`: return a validated read-only narrative/widget
  response or sanitized unavailability.
- `POST /api/v1/assistant/tag-suggestion`: bounded server-grounded category API;
  it is not called by V1 web.
- Recovery export, preview and restore routes: protect client-side encrypted,
  explicit recovery operations.

## Current deployment

- PWA: Vercel Hobby project rooted at `apps/web`.
- API: separate Vercel Hobby project rooted at `apps/api`.
- Auth and ledger: the `artha-production` Supabase project with Postgres and
  RLS.
- AI: Gemini called by FastAPI through the official Google SDK; the browser
  never receives the provider key.
- Source and CI: public GitHub repository and GitHub Actions.

Manual entry, dashboards and confirmed ledger history remain available when the
LLM is not configured. Natural-language capture and the assistant do not: Quick
Add opens manual recovery with preserved text, while assistant requests fail
closed with a sanitized error.

The checked-in Render blueprint remains an optional container-hosting fallback,
not the current production topology. Free plans have usage and privacy limits;
they must fail closed and must never silently enable billing.

Current official references: [Vercel Hobby](https://vercel.com/docs/plans/hobby),
[Vercel FastAPI](https://vercel.com/docs/frameworks/backend/fastapi),
[Vercel monorepos](https://vercel.com/docs/monorepos),
[Supabase pricing](https://supabase.com/pricing),
[Supabase RLS](https://supabase.com/docs/guides/database/postgres/row-level-security),
and [Ollama structured output](https://docs.ollama.com/capabilities/structured-outputs).

## Repository shape

```text
artha/
  apps/
    web/                 # React PWA
    api/                 # FastAPI application
  supabase/
    migrations/          # schema, RLS and atomic RPC functions
    tests/               # SQL contract assertions
  docs/
    assets/              # repository-owned architecture visual
    artifacts/           # versioned architecture and QA evidence
  evals/                 # fictional model evaluation data
  .github/workflows/     # continuous integration
```

The ledger, not the model, is Artha's source of financial truth.
