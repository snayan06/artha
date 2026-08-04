# Hisab task list

Updated: 4 August 2026

## Milestone 0 — repository foundation

- [x] Create Desktop monorepo and local Git repository.
- [x] Preserve product requirements and overall system architecture.
- [x] Add environment template, repository rules and standard commands.
- [ ] Publish a sanitized fresh-history public GitHub repository and verify `main`.
- [x] Add CI workflow for web and API checks.

## Milestone 1 — trustworthy ledger API

- [x] Add FastAPI application with health and version endpoints.
- [x] Add typed models for accounts, transactions, drafts, splits and dashboard.
- [x] Store every amount as integer paise.
- [x] Keep opening balances explicit and derive current balances from movements.
- [x] Implement debit, credit and transfer semantics.
- [x] Implement shared expenses: full cash movement, member splits and receivables.
- [x] Implement correction and soft deletion in the local API.
- [x] Add idempotency protection for confirmed writes and concurrent demo startup.
- [ ] Add demo SQLite repository and production Supabase repository boundary.
- [x] Test balance, transfer, credit-card and split invariants in the local API.

## Milestone 2 — five-second capture

- [x] Parse debit/credit language, INR amounts and known account names.
- [x] Parse equal-split phrases and configured member names.
- [x] Return an unsaved draft with confidence and warnings.
- [x] Require explicit confirmation before writing.
- [x] Remember merchant/category/account defaults through an explicit prospective rule.
- [x] Check learned merchant rules before requesting an LLM suggestion.
- [x] Constrain LLM tagging output to existing household categories with confidence.
- [x] Fall back to manual review when parsing is incomplete.
- [x] Keep the flow functional without an AI provider.

## Milestone 3 — mobile PWA

- [x] Add responsive application shell and bottom navigation.
- [x] Add onboarding for household members, accounts, cards and opening balances.
- [x] Add Home balance summary and six-month trend chart.
- [x] Add conversational Quick Add and parsed review card.
- [x] Add transaction list, search and filters.
- [x] Add the household member-balance screen and unsettled activity.
- [x] Add installable manifest and icons.
- [x] Add accessible error and confirmation states with touch-sized controls.

## Milestone 4 — Supabase and security

- [x] Create tables, constraints, indexes and updated-at triggers.
- [x] Enable RLS on every exposed table.
- [x] Add user/household membership policies.
- [x] Add atomic confirmation, transfer and settlement functions.
- [x] Add read-only account-balance function.
- [x] Document magic-link authentication integration.
- [x] Keep service-role and AI secrets out of browser configuration.

## Milestone 5 — integration and release gate

- [x] Seed realistic demo data without personal financial information.
- [x] Verify Quick Add → review → confirm → dashboard update.
- [x] Verify editing a shared expense recalculates all derived totals.
- [x] Verify settlement does not change spending or income.
- [x] Run API tests, web tests, lint, type checks and production build.
- [x] Re-run responsive QA after onboarding/theme changes at narrow mobile, mobile and desktop widths.
- [x] Document deployment steps for Pages, Render and Supabase.
- [x] Record remaining V1 limitations explicitly.

## Assistant preview and V2

- [ ] Invite selected participants as authenticated household members.
- [x] Add hosted Qwen3.6-27B and local Qwen3 4B provider adapters.
- [x] Add analytics assistant with user-scoped read-only summaries.
- [x] Return validated metric, chart and transaction-table schemas.
- [ ] Show evidence date range, source count and matching transactions.
- [ ] Add evaluation cases for totals, comparisons and affordability questions.
- [ ] Add optional Telegram/WhatsApp capture adapter.
- [ ] Add investments, liabilities and net-worth model.
