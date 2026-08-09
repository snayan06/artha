# Account management production release

Date: 10 August 2026  
Release: `41b53b800a16b9c383ef5152a2afbdff7b8ca809`  
Pull requests: [#27](https://github.com/snayan06/artha/pull/27),
[#28](https://github.com/snayan06/artha/pull/28)

## Outcome

Post-onboarding account and card maintenance is deployed on the production web
and API domains. A signed-in owner can add, rename, archive and restore
zero-balance money sources, maintain credit-card details and reconcile a
displayed balance through an append-only audited adjustment. Existing opening
balances and transaction history are never rewritten.

The production database was migrated before the application release. Account
mutations use exact request hashes and idempotency keys, and every write that
can change an account balance shares the same per-account locking protocol.
Archived accounts cannot receive new balance-changing writes.

## Verification evidence

- Local `make check` passed: 208 web tests, 280 API tests, production PWA build,
  all 12 migrations and six SQL contracts, plus 60 capture, 30 auto-tag, 24
  assistant and 49 router dataset contracts.
- Production migration history matches the repository. Remote schema
  assertions, account idempotency behavior and account-write locking contracts
  passed against the exact Artha project; database lint reported no schema
  errors.
- PR #28 CI run
  [31332145201](https://github.com/snayan06/artha/actions/runs/31332145201)
  passed Web, API and disposable-Supabase runtime jobs. CodeQL run
  [31332145212](https://github.com/snayan06/artha/actions/runs/31332145212)
  passed JavaScript/TypeScript and Python.
- Main CI run
  [31332275508](https://github.com/snayan06/artha/actions/runs/31332275508)
  and CodeQL run
  [31332275498](https://github.com/snayan06/artha/actions/runs/31332275498)
  passed for the exact release SHA.
- Both Vercel production deployments completed for the release SHA. The
  [web app](https://artha-web-one.vercel.app/),
  [Settings route](https://artha-web-one.vercel.app/settings) and
  [API health](https://artha-api-mu.vercel.app/health) returned HTTP 200.

## Signed-in production acceptance

The acceptance used the existing private test session and recorded only
sanitized assertions; no account names, balances, emails or screenshots were
stored in the repository.

- The Settings account list loaded with current balances and available-credit
  summaries.
- A same-name add attempt was rejected without creating a row, preserved the
  form and displayed `An active account with this name already exists.`
- The balance-reconciliation and account-detail editors opened and cancelled
  without a write.
- A temporary zero-balance QA row created while diagnosing a test-selector
  mistake was archived. It had no transactions, and the active canonical-name
  collision count is zero.
- The dark Settings page stayed within the effective mobile viewport with no
  horizontal overflow; primary regions and account cards remained inside the
  viewport.

## Scope still open

This release closes owner account/card maintenance, not the remaining personal
release guards. Two-owner hosted isolation, final-domain restore into a fresh
household, full browser-process reopen, real provider-unavailable recovery,
sanitized log/latency evidence and real-data privacy approval remain open.
Transaction correction/delete, participant maintenance, settlements and invited
family access are planned follow-up slices.
