# Artha project checkpoint

Updated: 5 August 2026, 00:56 IST

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

**Status: release candidate green; production merge intentionally held.**

Do not enter real financial data yet. The new logical-ledger migration must be
applied to Supabase before the API changes reach production.

| Surface | Current state |
| --- | --- |
| Production `main` | Still at `0fa2013`; current live application is unchanged |
| Local release commits | `0393be8` and `61c59db` on local `main` |
| Public release candidate | PR [#11](https://github.com/snayan06/artha/pull/11); use the PR head as the current public release commit |
| GitHub checks | Web, API, SQL, CodeQL and both Vercel previews green |
| Supabase migration | `20260805010000_logical_ledger_activity.sql` not yet applied remotely |
| Deployment blocker | Supabase CLI waits on macOS Keychain authorization without terminal output |

## Morning resume checklist

Work in this order. Do not merge first.

- [ ] User is at the Mac and ready to approve one Keychain dialog locally.
- [ ] Run `supabase migration list --linked`.
- [ ] If macOS asks, the user enters the Mac login password directly and chooses
  the appropriate allow option. The password is never sent to Codex or chat.
- [ ] Run `supabase db push --linked --dry-run` and confirm that only
  `20260805010000_logical_ledger_activity.sql` is pending.
- [ ] Run `supabase db push --linked` and wait for success.
- [ ] Re-run `supabase migration list --linked` and store sanitized evidence.
- [ ] Confirm PR #11 checks are still green, then merge it into `main`.
- [ ] Verify production API health, web routing, security headers and Mumbai
  execution.
- [ ] Complete authenticated login, reopen, sign-out, transfer and account-filter
  smoke tests using fictional data.
- [ ] Update this checkpoint, the sprint board and the QA artifact with the final
  result.

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
Local web: 12 files, 80 tests passed
Local API: 96 tests passed
Quality: ESLint, TypeScript, Ruff and strict mypy passed
Build: production PWA passed without the previous bundle-size warning
SQL: 6 migrations, seed and 2 SQL contract tests parsed
Capture evaluation: 50 fictional cases valid; hosted model not called
Manual UI: 320 px, 390 px and desktop checks passed in light/dark
Browser console: no warnings or errors during the checked flows
PR #11: all GitHub and Vercel preview checks green
```

Detailed evidence: [Sprint 1 reliability batch](artifacts/qa/2026-08-05-reliability-batch.md).

## Product and engineering decisions to preserve

- Current scope is personal use with friends/family participating in expense
  splits. Separate invited-user access is Sprint 2, not a Sprint 1 dependency.
- Money is integer paise. Transfers and card payments are not spending or income.
- Natural-language and LLM parsing only create unsaved review drafts. A user must
  explicitly confirm every ledger write.
- Deterministic parsing remains available without a model. Hosted Qwen is not
  enabled until the 50-case benchmark is run and reviewed.
- Multiple banks/cards are first-class accounts. Post-onboarding account editing
  belongs in **Accounts & family** settings.
- Production order is always database migration → application deployment →
  authenticated acceptance. Never deploy code that depends on an absent RPC.
- Never claim production is green until final-domain authentication, two-owner
  isolation, responsive QA, recovery and export/restore gates pass.

## Remaining user actions

Only ask for these when the engineering work reaches the corresponding gate:

1. Approve the local macOS Keychain dialog for the Supabase CLI.
2. Later, use a second fictional test identity for household-isolation acceptance.
3. Later, create a Groq key and enter it directly in the deployment secret store;
   never paste it into chat or source control.

## Next engineering priorities

1. Apply the logical-ledger migration and deploy PR #11 safely.
2. Finish final-domain login/session and two-owner isolation acceptance.
3. Complete the full mobile/desktop light/dark matrix for every screen.
4. Run the hosted Qwen benchmark and review critical-field error slices.
5. Build **Accounts & family** management.
6. Add invitation/RLS support only after the personal pilot is trustworthy.
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
| 5 Aug 2026 | Release candidate implemented, manually checked, published as PR #11 and fully green; production held for Supabase migration authorization |
