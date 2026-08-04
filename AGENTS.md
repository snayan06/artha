# Artha repository guidance

## Product invariants

- Money is stored as integer paise, never floating point.
- Natural-language capture always creates an unsaved draft.
- A transaction is written only after explicit confirmation.
- Account movement and personal expense share are separate concepts.
- Credit-card payments are transfers, not a second expense.
- Settlements clear receivables/payables and are not income or expense.
- V1 has one authenticated owner and zero or more split participants without logins.
- V2 agent tools are read-only and return source-linked, validated UI data.

## Repository boundaries

- `apps/web`: React PWA. Do not embed secrets or financial calculations here.
- `apps/api`: FastAPI application and deterministic business logic.
- `supabase`: production Postgres schema, functions and RLS policies.
- `docs`: product, architecture, decisions and maintained task list.

## Quality gate

Run `make check` before calling a change complete. Keep unit tests around ledger invariants and parser behaviour. Never commit `.env`, credentials, generated databases or user financial data.
