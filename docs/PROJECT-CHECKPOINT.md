# Artha project checkpoint

Updated: 7 August 2026, 01:08 IST

This is the first document to read when starting or resuming Artha work. It is
the concise handoff between the user and Codex. Use the
[sprint board](SPRINT-BOARD.md) for ordered sprint execution and
[task list](TASKS.md) for the complete backlog.

## How to maintain this checkpoint

After every meaningful work batch:

1. Update the timestamp and current release state.
2. Record what changed, how it was verified and the next exact action.
3. Keep the morning/run-resume checklist current.
4. Link detailed evidence instead of copying large reports here.
5. Never include passwords, tokens, email links, real balances or private
   financial data.

## Current release state

**Status: V1 is live and the authenticated fictional-data production journey is green.**

Do not enter real financial data yet. New and returning login, onboarding,
financial flows, Gemini capture/assistant behavior, encrypted export and the
responsive page sweep passed on the final domain. Two-owner isolation and a
final-domain restore into a fresh household remain the release guard.

| Surface | Current state |
| --- | --- |
| Production `main` | Merge `0376b60`; release PRs [#16](https://github.com/snayan06/artha/pull/16), [#17](https://github.com/snayan06/artha/pull/17) and [#18](https://github.com/snayan06/artha/pull/18) are merged |
| GitHub checks | Both Vercel checks passed on every release PR. GitHub did not create the required Web/API/SQL runs, so the owner merge override was used only after the identical full local gate passed |
| Vercel | Web and API production aliases serve the current release successfully from Mumbai |
| Supabase RPC catalog | The exact `artha-production` project now resolves balances, logical activity, encrypted export and atomic restore RPCs |
| Public checks | API health and web return `200`; anonymous catalog probes resolve both required ledger RPCs without exposing ledger data |
| Authenticated journey | New-user magic link, returning-user link, session persistence, sign-out and restored server-owned onboarding passed with fictional data |
| Financial journey | Backdated split expense, `25k` income, `25k` transfer, card expense, filters and live dashboard/member updates passed |
| Gemini production | `gemini-3.5-flash-lite` returned grounded capture drafts and read-only metric/chart UI; hosted fictional gates remain 50/50, 30/30 and 24/24 |
| Responsive/theme | Home, Transactions, Quick Add, Shared, Assistant and Settings have no horizontal overflow at 320, 390 or 1440 CSS px; light/dark switching and mobile/desktop dark UI passed |
| Remaining gate | Two-owner hosted isolation, encrypted restore into a fresh/empty production household and sanitized log/latency evidence |

## Resume checklist

- [x] Apply and verify `20260805010000_logical_ledger_activity.sql` remotely.
- [x] Merge PR #11 and pass fresh main CI, CodeQL and Vercel deployments.
- [x] Verify public API health, web routing and baseline security headers.
- [x] Verify the deployed `list_ledger_activity` and `get_account_balances`
  endpoints resolve through PostgREST instead of returning `PGRST202`.
- [x] Complete authenticated login, reopen, sign-out, transfer and account-filter
  smoke tests using fictional data.
- [ ] Complete two-owner hosted isolation.
- [x] Complete the final-domain 320 px, 390 px and 1440 px primary-page sweep.
- [x] Implement client-side encrypted export/restore with an empty-household
  restore guard and local SQL round-trip contract.
- [x] Consolidate Gemini PR #15 and dependency PRs #8-#10 into one tested release.
- [x] Apply `20260806030000_encrypted_recovery.sql` to the exact Artha production
  project before deploying the application code that exposes recovery.
- [x] Merge and deploy the consolidated release; verify Gemini capture and
  assistant requests plus the hosted auto-tag gate.
- [x] Download a client-side encrypted final-domain backup with fictional data.
- [ ] Restore that backup into a fresh/empty production household and compare totals.
- [ ] Begin S2-01 owner-only **Accounts & family** settings after the acceptance gate.

## Completed in the current release candidate

- Explicit expired/reused magic-link, wrong-browser PKCE, invalid-callback and
  stale-session recovery.
- Server-owned onboarding/profile hydration for returning users.
- Correct `25k` → ₹25,000 transfer capture with source and destination accounts.
- Atomic idempotent transfers and pair-safe logical activity pagination.
- Transaction history filtering for banks/cards, including both transfer sides.
- Truthful offline state and baseline web/API security headers.
- A 50-case fictional capture dataset plus a provider-neutral hosted evaluation
  runner, preserving the Qwen baseline and sanitized outcome/field/tag slices.
- A Gemini provider adapter shared by capture, allow-listed auto-tagging and the
  validated read-only assistant, with fictional hosted gates of 50/50, 30/30
  and 24/24 respectively.
- Client-side encrypted export and preview-before-restore with an atomic,
  empty-household-only database restore boundary.
- Web bundle split: the main JavaScript chunk fell from 520 KB to 304 KB.
- Updated product, architecture, UI, backend, database and QA artifacts.

## Verification checkpoint

```text
Local web after production QA fixes: 16 files, 103 tests passed
Local API after recovery and Gemini: 122 tests passed
Quality: ESLint, TypeScript, Ruff and strict mypy passed
Build: production PWA passed without the previous bundle-size warning
SQL: 7 migrations, seed and 2 SQL contract tests parsed
Recovery SQL: 8 migrations and 4 SQL contract tests parsed; blank-local-database migration and direct SQL contracts passed
AI contracts: 50 capture, 30 auto-tag and 24 assistant cases valid
Hosted Gemini evidence: capture 50/50, auto-tag 30/30, assistant 24/24 on fictional data
Manual UI: all 6 primary pages fit at 320 px, 390 px and 1440 px; theme switching plus mobile/desktop dark visual review passed
Production: PRs #16-#18 merged; all web/API Vercel preview and production deployments are ready
Public smoke: web root, transactions and assistant routes return 200; API health returns 200 from Mumbai
Recovery: exact production project resolves all four required RPCs without a PGRST202 catalog miss
Telemetry: Vercel Web Analytics and Speed Insights are mounted with tested query/fragment redaction
Authenticated production: new/returning magic link, persisted session, sign-out/re-login and server-owned onboarding passed
Financial production: expense, income, transfer, card, backdate, split, filters and live chart/member updates passed
Gemini production: grounded capture plus metric/chart assistant responses passed with fictional data
```

Detailed evidence: [Sprint 1 reliability batch](artifacts/qa/2026-08-05-reliability-batch.md).

## Product and engineering decisions to preserve

- Current scope is personal use with friends/family participating in expense
  splits. Separate invited-user access is Sprint 2, not a Sprint 1 dependency.
- Money is integer paise. Transfers and card payments are not spending or income.
- Natural-language and LLM parsing only create unsaved review drafts. A user must
  explicitly confirm every ledger write.
- Deterministic parsing remains available without a model. Gemini is selected
  for the fictional private-pilot evaluation after full capture, auto-tag and
  assistant gates; free-tier Gemini must not receive real family-finance text.
- Private capture learning history is planned as default-on with clear notice,
  Settings disable/delete/export controls and no external training/public use
  without separate consent.
- Multiple banks/cards are first-class accounts. Post-onboarding account editing
  belongs in **Accounts & family** settings.
- Production order is always database migration → application deployment →
  authenticated acceptance. Never deploy code that depends on an absent RPC.
- Never claim production is green until final-domain authentication, two-owner
  isolation, responsive QA, recovery and export/restore gates pass.

## Remaining user actions

Only ask for these when the engineering work reaches the corresponding gate:

1. Use a second fictional test identity for household-isolation acceptance.
2. Restore the encrypted backup into that identity's fresh/empty household.
3. The production Gemini key is configured server-side. Add the same variable
   to the ignored local `.env` only when local hosted evaluation is needed.

## Next engineering priorities

1. Finish two-owner isolation and final-domain restore acceptance.
2. Record sanitized browser/API log redaction and authenticated cold/warm latency.
3. Build S2-01 through S2-05 **Accounts & family** owner management.
4. Re-run the personal four-bank/multiple-card setup when the owner is ready to replace fictional QA data.
5. Add invitation/RLS support only after owner-only hardening passes.
6. Add the private capture-feedback learning loop.

## Source-of-truth map

| Need | Document |
| --- | --- |
| Current handoff and resume point | This file |
| Ordered sprint execution | [SPRINT-BOARD.md](SPRINT-BOARD.md) |
| Full backlog | [TASKS.md](TASKS.md) |
| Product requirements | [product-requirements.md](product-requirements.md) |
| System architecture | [system-architecture.md](system-architecture.md) |
| Database structure | [database-schema.md](database-schema.md) |
| Deployment procedure | [DEPLOYMENT.md](DEPLOYMENT.md) |
| Decisions | [DECISIONS.md](DECISIONS.md) |
| Detailed evidence | [artifacts/](artifacts/) |

## Checkpoint log

| Date | Checkpoint |
| --- | --- |
| 7 Aug 2026 | Merged and deployed PRs #16-#18; completed real magic-link new/returning login, server-owned onboarding, fictional expense/income/transfer/card/split flows, transaction filters, Gemini capture/assistant, encrypted export and 320/390/1440 responsive acceptance; fixed live chart/member refresh and mobile chart overflow found during QA |
| 7 Aug 2026 | Consolidated Gemini and dependency PRs onto encrypted recovery; full local gate passed with 98 web and 122 API tests plus 104 AI dataset contracts; applied and catalog-probed the exact production recovery migration; production Gemini variables configured pending deployment |
| 7 Aug 2026 | Implemented encrypted export/restore, Settings recovery UI, recovery RPCs and two-household/round-trip SQL contracts; full local gate passed with 98 web and 112 API tests; production migration and consolidated Gemini release remain |
| 6 Aug 2026 | Deployed and merged PR #13; full local gate, CodeQL, Vercel, public routing, API health and both live RPC probes passed; GitHub Web/API/SQL runners remained queued during the GitHub Actions outage |
| 6 Aug 2026 | Recovered the production ledger RPC catalog, verified both required functions through the deployed REST endpoint and added exact-project release guards |
| 6 Aug 2026 | Logical-ledger migration applied; PR #11 merged; main CI, CodeQL, Vercel and public health/routing checks green; Sprint 2 contract and Qwen baseline recorded |
| 5 Aug 2026 | Release candidate implemented, manually checked, published as PR #11 and fully green; production held for Supabase migration authorization |
