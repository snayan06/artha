# Sprint 1 reliability batch

Date: 5 August 2026
Status: local acceptance passed; deployment and authenticated acceptance pending

## Outcomes completed

- Magic-link failures now distinguish expired/reused links, wrong-browser PKCE
  callbacks, invalid callbacks and expired stored sessions.
- Logical ledger activity is constructed and paginated inside Postgres, after
  both transfer rows have been joined.
- Transaction history can be filtered by any bank/card account and treats both
  transfer endpoints as account activity.
- The hosted capture-model evaluator validates all 50 fictional cases without a
  key and can produce sanitized field, outcome and tag slices when Qwen is run.
- Offline state is visible and does not imply that unsaved V1 changes are queued.
- Sensitive API payloads receive `no-store`; web and API security headers are
  configured.

## Automated acceptance

```text
Web: 12 files, 80 tests passed
API: 96 tests passed
Python: Ruff and strict mypy passed
Web: ESLint, TypeScript and production PWA build passed
SQL: 6 migrations, seed and 2 contract tests parsed
Capture dataset: 50 cases valid in both validators; model not called
git diff --check: passed
```

The PWA build separates the Supabase auth client into its own cacheable chunk.
The main JavaScript chunk fell from 520 KB to 304 KB and the previous bundle-size
advisory is gone.

## Manual responsive acceptance

The local demo was exercised in the in-app browser:

| View | Theme | Result |
| --- | --- | --- |
| Transactions, 320 × 800 | Light and dark | No horizontal overflow; account control present |
| Transactions, 390 × 844 | Dark | Account selector remained within 33–357 px; no overflow |
| Home, 1440 × 900 | Light and dark | No out-of-viewport cards; no overflow |

Selecting **HDFC UPI** returned two matching fictional expenses, proving the
account interaction rather than only inspecting its appearance. Browser logs
contained no warnings or errors.

## Remaining acceptance

- Apply the new migration to Supabase and verify its RPC contract against real
  Postgres; Docker was not running for a local Supabase database test.
- Deploy web/API, verify headers and confirm production health.
- Complete magic-link, reopen, sign-out, two-owner isolation and authenticated
  transfer smoke tests using fictional identities.
- Run hosted Qwen only after its key is entered directly into the deployment
  secret store.
