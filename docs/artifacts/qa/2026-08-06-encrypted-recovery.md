# Encrypted recovery and isolation acceptance

Date: 6 August 2026

## Result

The recovery implementation is locally green. Production deployment and the
two-real-identity final-domain run remain pending and must not be inferred from
this local evidence.

| Gate | Result | Evidence |
| --- | --- | --- |
| Blank database migration | Pass | All eight migrations applied from scratch in local Supabase |
| Recovery model/API | Pass | 112 API tests total; 21 targeted recovery/route cases |
| Browser encryption | Pass | 7 WebCrypto tests: fidelity, tamper, wrong passphrase, strict container and size guards |
| Recovery UI | Pass | Export, preview, explicit confirmation and blocker component tests |
| Session remount | Pass | Auth provider reacquired the persisted Supabase session after remount |
| Household isolation | Pass locally | Two fictional owners saw only their own profile, household, members and accounts; cross-RPC and cross-write probes were denied |
| Ledger round trip | Pass locally | Expense, split, transfer pair, rule and audit facts restored to fresh IDs |
| Derived balances | Pass locally | Restored fictional balances were exactly ₹680 and ₹700 |
| Restore retry | Pass locally | Same idempotency key returned the first restored household |
| Responsive UI | Pass locally | 320 px, 390 px and 1440 px; light/dark; no horizontal overflow or console errors |

## Commands represented by this evidence

- `make check`
- each `supabase/tests/*.sql` contract executed with stop-on-error against the
  local Supabase Postgres container;
- production Vite build;
- manual browser pass on onboarding and Settings recovery surfaces.

No real user, email, account, balance, token or production export appears in
this artifact. Hosted acceptance is performed by
`scripts/check_two_household_tokens.py`, which accepts two short-lived access
tokens only from a protected local process and prints a sanitized result.
