# Artha task list

Start with [`PROJECT-CHECKPOINT.md`](PROJECT-CHECKPOINT.md) for the current
handoff and release guard.

Updated: 7 August 2026

For the current ordered delivery view, blockers and user actions, see
[`SPRINT-BOARD.md`](SPRINT-BOARD.md). This file remains the complete backlog.

## Live launch status

**Current stage:** V1 is live and the authenticated fictional-data journey is green. Do not enter real financial data until every remaining P0 security/recovery item below is complete.

- [x] Public GitHub repository and CI/CodeQL workflows created under `snayan06/artha`.
- [ ] Restore reliable GitHub Actions triggering and obtain fresh green `main` CI/CodeQL runs; do not normalize owner overrides.
- [x] React PWA, FastAPI API, database migrations, RLS policies and automated test suites are implemented.
- [x] Personal Vercel account created under the intended owner.
- [x] Personal Supabase account and organization confirmed; the explicitly approved legacy projects `inventory_management` and `VectorDb` were permanently deleted.
- [x] Create the fresh `artha-production` Supabase project in Mumbai.
- [x] Apply all migrations and pass hosted catalog/RLS schema assertions.
- [ ] Complete anonymous-denial and two-household behavioural isolation on the hosted database.
- [x] Create and configure the `artha-api` and `artha-web` Vercel projects.
- [x] Pass final-domain authentication, financial-flow and responsive-layout acceptance with fictional data.
- [ ] Pass two-owner isolation and encrypted restore acceptance.

**Next action:** prove two-owner isolation, then restore the encrypted fictional backup into a fresh/empty production household.

## Current execution queue

### P0 — required before entering real financial data

1. **Lock the free hosting architecture.**
   - [x] Record the final PWA, API and Supabase hosting choice in an architecture decision.
   - [x] Document target account ownership, free-tier limits, sleep behavior and upgrade risks.
   - Done when: every production surface has one named owner, provider and expected URL.
2. **Create and secure the personal Supabase environment.**
   - [x] Confirm the personal Supabase account and organization are owned by the intended user.
   - [x] Permanently remove the two explicitly approved unrelated projects from that organization.
   - [x] Create a fresh Artha project under the correct personal account.
   - [x] Apply all versioned migrations from an empty database.
   - [x] Pass hosted schema lint and catalog/RLS assertions.
   - [ ] Re-run anonymous-denial and two-household isolation tests.
   - Done when: sanitized RLS evidence is stored in `docs/artifacts/qa/`.
3. **Deploy the API and PWA.**
   - [x] Deploy FastAPI with production mode and server-only secrets.
   - [x] Deploy the React PWA with the Supabase publishable key and exact API origin.
   - [x] Configure exact CORS origins and Supabase magic-link redirects.
   - Done when: health, login, onboarding and confirmed capture work on final URLs.
4. **Complete authentication acceptance.**
   - [x] Verify magic-link login, navigation/reload persistence, sign-out and returning-user sign-in.
   - [ ] Verify two different users can independently onboard and see only their own households.
   - [ ] Keep same-household member invitations disabled until the V2 authorization flow is complete.
   - Done when: the final-domain isolation scenario passes with two real test identities.
5. **Complete recovery and production QA.**
   - [x] Implement encrypted export and tested local restore.
   - [x] Execute the authenticated production happy path and every primary page with fictional data.
   - [x] Recheck all six primary pages at 320 px, 390 px and 1440 px; verify light/dark switching and mobile/desktop dark UI.
   - [ ] Restore a downloaded encrypted backup into a fresh/empty production household.
   - Done when: recovery evidence, final URLs and the signed-off QA report are recorded.

### P1 — private-pilot improvements

- [x] Add a versioned 50-case fictional capture/parser dataset and CI contract checker.
- [x] Add deterministic and hosted-provider scoring runners with sanitized accuracy/error slices.
- [ ] Add edit, correction and soft-delete controls to the UI for the existing API operations.
- [ ] Show assistant evidence date range, source count and matching transactions.
- [ ] Add representative assistant evaluation cases for totals, comparisons and affordability.
- [x] Run capture, auto-tag and assistant hosted benchmarks before selecting the pilot model.
- [x] Select Gemini 3.5 Flash-Lite for fictional pilot traffic and configure it server-side only.
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
- [x] Add a per-account activity filter that includes both sides of transfers.
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
- [x] Add explicit expired-link, wrong-browser callback and stale-session recovery states.
- [x] Add no-store financial responses and baseline web/API security headers.
- [x] Keep service-role and AI secrets out of browser configuration.

## Milestone 5 — integration and release gate

- [x] Seed realistic demo data without personal financial information.
- [x] Verify Quick Add → review → confirm → dashboard update.
- [x] Verify editing a shared expense recalculates all derived totals.
- [x] Verify settlement does not change spending or income.
- [x] Run API tests, web tests, lint, type checks and production build.
- [x] Page logical transfer activity in Postgres after transfer-pair collapse.
- [x] Re-run responsive QA after onboarding/theme changes at narrow mobile, mobile and desktop widths.
- [x] Document deployment steps for Pages, Render and Supabase.
- [x] Record remaining V1 limitations explicitly.
- [x] Maintain a V1 QA matrix covering happy paths, financial invariants and edge cases.

## Milestone 6 — Artha private-pilot launch

- [x] Rename the product, packages, environment variables and documentation from Artha's former working name.
- [x] Select Vercel Hobby for the PWA/API plus Supabase Free; retain Render as a documented container fallback.
- [x] Create personal hosting and Supabase accounts with no legacy account ownership.
- [x] Create a fresh Artha Supabase project and apply all versioned migrations.
- [ ] Repeat anonymous-denial and two-household RLS isolation against the fresh project.
- [x] Deploy the FastAPI API and React PWA, then configure exact CORS and magic-link redirect origins.
- [x] Add the server-side Gemini key and model configuration without exposing it to the browser.
- [x] Test login, returning login, multi-account/card onboarding, backdated capture, transfer and family splits on the final domain.
- [ ] Repeat account setup with the owner's full four-bank/multiple-card configuration before replacing fictional QA data.
- [x] Verify every primary page at 320 px and 390 px plus 1440 px desktop, including explicit light/dark switching.
- [x] Implement encrypted export/restore and pass the local recovery drill.
- [x] Download a client-side encrypted fictional backup on the final domain.
- [ ] Repeat the encrypted recovery drill with fictional data on the final domain before entering real financial data.
- [x] Record final URLs, ownership and environment inventory in `docs/artifacts/qa/`; keep adding acceptance evidence as tests pass.

## Assistant preview and V2

- [ ] Add post-onboarding **Accounts & family** management.
  - [ ] Let users add, rename and archive bank, cash and wallet accounts after initial setup.
  - [ ] Let users add and update credit-card names, limits, statement days and payment due days.
  - [ ] Record balance corrections as explicit audited adjustments; never silently rewrite an opening balance or transaction history.
  - [ ] Let users add, rename and deactivate non-login family participants used for splits.
  - [ ] Keep authenticated household invitations and roles as a separate authorization flow.
  - [ ] Cover empty, duplicate-name, outstanding-over-limit and archived-account edge cases.
  - [ ] Verify the management screens at 320 px, 390 px and desktop in light and dark modes.
- [ ] Invite selected participants as authenticated household members.
- [x] Add Gemini, hosted Groq/open-weight and local Ollama provider adapters.
- [x] Add analytics assistant with user-scoped read-only summaries.
- [x] Return validated metric, chart and transaction-table schemas.
- [ ] Show evidence date range, source count and matching transactions.
- [ ] Add evaluation cases for totals, comparisons and affordability questions.
- [x] Build versioned fictional capture, auto-tag and assistant benchmarks and select Gemini for the pilot from measured results.
- [ ] Add optional Telegram/WhatsApp capture adapter.
- [ ] Add investments, liabilities and net-worth model.
