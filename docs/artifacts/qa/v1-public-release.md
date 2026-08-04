# V1 public-release verification

Date: 4 August 2026  
Baseline commit: `fe304f7`

## Automated acceptance

- Web lint, TypeScript checks, 25 tests and production PWA build passed.
- API Ruff, strict mypy and 56 tests passed.
- All Supabase migration files passed PostgreSQL syntax validation.
- GitHub CI passed for web, API and Supabase SQL jobs.
- GitHub CodeQL passed for JavaScript/TypeScript and Python.
- The public repository had no open dependency security alerts at verification.

## Responsive acceptance

- Checked narrow mobile, 390 px mobile and 1440 px desktop layouts.
- Checked onboarding, Home, text capture, manual capture and Assistant flows.
- Checked Light, Dark and System theme behavior.
- No horizontal page overflow was observed at the tested widths.

## Functional acceptance

- Multi-account and credit-card onboarding calculates assets, liabilities and
  net position from opening balances.
- Natural-language capture accepts relative and explicit historical dates.
- Manual capture supports account, date, category and household splits.
- Confirmed entries update the dashboard and shared member balances.
- Assistant output is read-only and restricted to approved UI schemas.
- Auto-tagging applies deterministic household rules before an optional LLM
  suggestion and remains usable without an AI provider.

## Remaining production gate

This verifies the public V1 source and local application. Production acceptance
still requires a real Supabase project, authentication, deployed web/API URLs,
RLS checks with multiple users, and backup/restore verification on the final
environment.

