# Artha task list

Updated: 4 August 2026

## Current execution queue

### P0 — required before entering real financial data

1. **Lock the free hosting architecture.**
   - [ ] Record the final PWA, API and Supabase hosting choice in an architecture decision.
   - [ ] Document account ownership, free-tier limits, sleep behavior and upgrade risks.
   - Done when: every production surface has one named owner, provider and expected URL.
2. **Create and secure the personal Supabase environment.**
   - [ ] Create a fresh Artha project under the correct personal account.
   - [ ] Apply all versioned migrations from an empty database.
   - [ ] Re-run anonymous-denial and two-household isolation tests.
   - Done when: sanitized RLS evidence is stored in `docs/artifacts/qa/`.
3. **Deploy the API and PWA.**
   - [ ] Deploy FastAPI with production mode and server-only secrets.
   - [ ] Deploy the React PWA with the Supabase publishable key and exact API origin.
   - [ ] Configure exact CORS origins and Supabase magic-link redirects.
   - Done when: health, login, onboarding and confirmed capture work on final URLs.
4. **Complete authentication acceptance.**
   - [ ] Verify magic-link login, session refresh, reload persistence and sign-out.
   - [ ] Verify two different users can independently onboard and see only their own households.
   - [ ] Keep same-household member invitations disabled until the V2 authorization flow is complete.
   - Done when: the final-domain isolation scenario passes with two real test identities.
5. **Complete recovery and production QA.**
   - [ ] Implement encrypted export and tested restore.
   - [ ] Execute every production-pending row in the V1 QA matrix.
   - [ ] Recheck 320 px, 390 px and desktop layouts in light and dark modes.
   - Done when: recovery evidence, final URLs and the signed-off QA report are recorded.

### P1 — private-pilot improvements

- [ ] Add edit, correction and soft-delete controls to the UI for the existing API operations.
- [ ] Show assistant evidence date range, source count and matching transactions.
- [ ] Add representative assistant evaluation cases for totals, comparisons and affordability.
- [ ] Run the 50-case hosted-model benchmark before locking the production model.
- [ ] Configure the selected hosted Qwen provider only after the benchmark and privacy review.
- [ ] Add authenticated invitations, roles and removal for multiple logins in one household.

### P2 — expansion after the private pilot

- [ ] Add optional WhatsApp or Telegram capture.
- [ ] Add investments, liabilities and net-worth tracking.

### Definition of done for every task

- The implementation, tests and relevant documentation are updated together.
- `make check` and GitHub CI pass.
- UI changes are checked on mobile and desktop in both themes.
- No secrets or real financial data appear in source, logs, fixtures or screenshots.
- Deployment or security work includes sanitized evidence under `docs/artifacts/qa/`.

## Milestone 0 — repository foundation

- [x] Create Desktop monorepo and local Git repository.
- [x] Preserve product requirements and overall system architecture.
- [x] Add environment template, repository rules and standard commands.
- [x] Publish a sanitized fresh-history public GitHub repository and verify `main`.
- [x] Add CI workflow for web and API checks.
- [x] Add a versioned documentation-artifact index and release evidence.

## Milestone 1 — trustworthy ledger API

- [x] Add FastAPI application with health and version endpoints.
- [x] Add typed models for accounts, transactions, drafts, splits and dashboard.
- [x] Store every amount as integer paise.
- [x] Keep opening balances explicit and derive current balances from movements.
- [x] Implement debit, credit and transfer semantics.
- [x] Implement shared expenses: full cash movement, member splits and receivables.
- [x] Implement correction and soft deletion in the local API.
- [x] Add idempotency protection for confirmed writes and concurrent demo startup.
- [x] Add demo SQLite repository and production Supabase REST/RPC repository boundary.
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
- [x] Maintain a V1 QA matrix covering happy paths, financial invariants and edge cases.

## Milestone 6 — Artha private-pilot launch

- [x] Rename the product, packages, environment variables and documentation from Artha's former working name.
- [ ] Select the final ₹0 hosting topology; compare the Vercel + Supabase recommendation against the documented container-hosting alternatives.
- [ ] Create personal hosting and Supabase accounts with no legacy account ownership.
- [ ] Create a fresh Artha Supabase project and apply all versioned migrations.
- [ ] Repeat anonymous-denial and two-household RLS isolation against the fresh project.
- [ ] Deploy the FastAPI API and React PWA, then configure exact CORS and magic-link redirect origins.
- [ ] Add the server-side Groq key and enable experimental Qwen3.6-27B without exposing it to the browser.
- [ ] Test login, onboarding, four bank accounts, multiple cards, backdated capture and family splits on the final domain.
- [ ] Verify mobile layouts at 320 px and 390 px plus desktop, including light and dark modes.
- [ ] Implement encrypted export/restore and complete a recovery drill before entering real financial data.
- [ ] Record final URLs, ownership, environment inventory and acceptance evidence in `docs/artifacts/qa/`.

## Assistant preview and V2

- [ ] Invite selected participants as authenticated household members.
- [x] Add hosted Qwen3.6-27B and local Qwen3 4B provider adapters.
- [x] Add analytics assistant with user-scoped read-only summaries.
- [x] Return validated metric, chart and transaction-table schemas.
- [ ] Show evidence date range, source count and matching transactions.
- [ ] Add evaluation cases for totals, comparisons and affordability questions.
- [ ] Build a representative 50-case Artha model benchmark covering Indian merchants, backdated entries, account selection, family splits, categories, tool choice and structured UI; compare Qwen3.6-27B with at least two current hosted alternatives before production lock-in.
- [ ] Add optional Telegram/WhatsApp capture adapter.
- [ ] Add investments, liabilities and net-worth model.
