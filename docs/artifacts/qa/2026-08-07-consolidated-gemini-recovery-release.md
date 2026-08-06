# Consolidated Gemini, recovery and telemetry release

Date: 7 August 2026

## Included

- Gemini-backed structured drafts, allow-listed auto-tagging and the read-only
  assistant, all behind validation and deterministic fallbacks.
- Client-side encrypted ledger export plus preview-before-restore for a new or
  empty household.
- Production recovery RPC migration and a catalog probe that supports both
  legacy JWT anon keys and current Supabase publishable keys.
- Vercel Web Analytics and Speed Insights in the React application shell.
- TypeScript 5.9-compatible owned `ArrayBuffer` inputs for Web Crypto recovery.

## Privacy boundary

The telemetry `beforeSend` hook removes the complete query string and fragment
from every URL. This prevents magic-link codes, access-token fragments and
conversation identifiers from being included in Vercel telemetry. Unit tests
cover token removal, route preservation and malformed-event rejection.

Financial content, transaction descriptions, balances, emails and model prompts
are not added as custom analytics events.

## Verification

```text
Web: 16 test files, 103 tests
API: 122 tests
AI datasets: 50 capture, 30 tagging, 24 assistant cases
Hosted Gemini: 50/50 capture, 30/30 tagging, 24/24 assistant on fictional data
Quality: ESLint, TypeScript, Ruff, strict mypy and production web build
Database: migrations, seeds, SQL contracts and encrypted-recovery round trip
```

The exact production Supabase project resolves all four recovery RPC names.
The consolidated release and both production-QA fixes are deployed through PRs
#16, #17 and #18.

## Remaining final-domain acceptance

- Prove two-owner isolation with a second fictional identity.
- Prove two-household isolation through the deployed application.
- Run encrypted export and restore on fictional final-domain data.
- Record sanitized browser/API log-redaction and cold/warm latency evidence.

These items must remain visibly pending until they are exercised against the
final deployment; local or catalog evidence is not a substitute.
