# Artha project checkpoint

Updated: 6 August 2026, 22:57 IST

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

**Status: Production ledger RPC recovered; authenticated acceptance remains.**

Do not enter real financial data yet. The ledger RPC outage and application
deployment are fixed, but final-domain login persistence, two-owner isolation
and recovery acceptance still require interactive testing.

| Surface | Current state |
| --- | --- |
| Production `main` | Merge `f1256f7`; PR [#13](https://github.com/snayan06/artha/pull/13) is merged |
| GitHub checks | PR CodeQL and both Vercel checks passed; Web/API/SQL runners were queued during a reported GitHub Actions outage, while the equivalent local gate passed |
| Vercel | Web and API production aliases serve the current release successfully from Mumbai |
| Supabase RPC catalog | The deployed project resolves `get_account_balances` and `list_ledger_activity`; exact-project migration-history access remains an owner-only operational requirement |
| Public checks | API health and web return `200`; anonymous catalog probes resolve both required ledger RPCs without exposing ledger data |
| Remaining gate | Authenticated login/reopen/sign-out, two-owner isolation and financial-flow smoke |

## Resume checklist

- [x] Apply and verify `20260805010000_logical_ledger_activity.sql` remotely.
- [x] Merge PR #11 and pass fresh main CI, CodeQL and Vercel deployments.
- [x] Verify public API health, web routing and baseline security headers.
- [x] Verify the deployed `list_ledger_activity` and `get_account_balances`
  endpoints resolve through PostgREST instead of returning `PGRST202`.
- [ ] Complete authenticated login, reopen, sign-out, transfer and account-filter
  smoke tests using fictional data.
- [ ] Complete two-owner hosted isolation and the remaining responsive matrix.
- [ ] Begin S2-01 owner-only **Accounts & family** settings after the acceptance
  gate; use the Sprint 2 artifacts and board IDs as the implementation contract.

## Completed in the current release candidate

- Explicit expired/reused magic-link, wrong-browser PKCE, invalid-callback and
  stale-session recovery.
- Server-owned onboarding/profile hydration for returning users.
- Correct `25k` → ₹25,000 transfer capture with source and destination accounts.
- Atomic idempotent transfers and pair-safe logical activity pagination.
- Transaction history filtering for banks/cards, including both transfer sides.
- Truthful offline state and baseline web/API security headers.
- A 50-case fictional capture dataset plus a hosted-Qwen evaluation runner with
  sanitized outcome, field and tag slices.
- Web bundle split: the main JavaScript chunk fell from 520 KB to 304 KB.
- Updated product, architecture, UI, backend, database and QA artifacts.

## Verification checkpoint

```text
Local web: 13 files, 86 tests passed
Local API: 99 tests passed
Quality: ESLint, TypeScript, Ruff and strict mypy passed
Build: production PWA passed without the previous bundle-size warning
SQL: 7 migrations, seed and 2 SQL contract tests parsed
Capture evaluation: 50 fictional cases valid; hosted baseline was 16/16 evaluated passes at 16/50 coverage
Manual UI: 320 px, 390 px and desktop checks passed in light/dark
Production: PR #13 merged; CodeQL and both Vercel checks green; GitHub Web/API/SQL jobs queued during an Actions outage
Public smoke: web root, transactions and assistant routes return 200; API health returns 200 from Mumbai
Recovery: deployed Supabase project resolves `get_account_balances` and
`list_ledger_activity`; API health remains 200
```

Detailed evidence: [Sprint 1 reliability batch](artifacts/qa/2026-08-05-reliability-batch.md).

## Product and engineering decisions to preserve

- Current scope is personal use with friends/family participating in expense
  splits. Separate invited-user access is Sprint 2, not a Sprint 1 dependency.
- Money is integer paise. Transfers and card payments are not spending or income.
- Natural-language and LLM parsing only create unsaved review drafts. A user must
  explicitly confirm every ledger write.
- Deterministic parsing remains available without a model. Hosted Qwen stays
  experimental until all 50 cases receive valid outcomes and the error slices
  pass; availability failures are reported separately from model correctness.
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

1. Complete final-domain sign-in/reopen/sign-out testing when prompted.
2. Use a second fictional test identity for household-isolation acceptance.
3. The local Groq key is configured safely; add it to Vercel only after the
   complete benchmark passes, never in chat or source control.

## Next engineering priorities

1. Finish final-domain login/session and two-owner isolation acceptance.
2. Complete the full mobile/desktop light/dark matrix for every screen.
3. Diagnose Qwen unavailability, resume the 50-case benchmark and review slices.
4. Build S2-01 through S2-05 **Accounts & family** owner management.
5. Add invitation/RLS support only after owner-only hardening passes.
6. Add the private capture-feedback learning loop.
7. Add encrypted export/restore before storing real financial data.

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
| 6 Aug 2026 | Deployed and merged PR #13; full local gate, CodeQL, Vercel, public routing, API health and both live RPC probes passed; GitHub Web/API/SQL runners remained queued during the GitHub Actions outage |
| 6 Aug 2026 | Recovered the production ledger RPC catalog, verified both required functions through the deployed REST endpoint and added exact-project release guards |
| 6 Aug 2026 | Logical-ledger migration applied; PR #11 merged; main CI, CodeQL, Vercel and public health/routing checks green; Sprint 2 contract and Qwen baseline recorded |
| 5 Aug 2026 | Release candidate implemented, manually checked, published as PR #11 and fully green; production held for Supabase migration authorization |
