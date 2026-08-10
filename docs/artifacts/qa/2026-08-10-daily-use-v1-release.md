# Daily-use V1 release evidence

Date: 10 August 2026
Status: local release candidate; publication and final-domain acceptance pending

This artifact records sanitized evidence only. It intentionally excludes real
emails, account or member labels, UUIDs, balances, transaction text, prompts,
tokens, secrets and backup contents.

## Production trust checks

Target: the explicitly configured Artha production Supabase project ending in
`…kjhz`. The locally linked CLI project was not used.

| Check | Production evidence | Result |
| --- | --- | --- |
| Two-household isolation and anonymous denial | `supabase/tests/003_two_household_isolation.sql` executed through the production pooler inside an explicit transaction | PASS; all fictional rows rolled back |
| Encrypted recovery round trip | `supabase/tests/004_recovery_round_trip.sql` executed through the production pooler inside an explicit transaction | PASS; export, fresh-owner restore, totals, transfer linkage and idempotent replay passed; all fictional rows rolled back |

## Clean starting point

Before the daily-use implementation began:

- web lint and TypeScript checks passed;
- 208 web tests passed;
- Ruff and strict mypy passed;
- 280 API tests passed;
- the production PWA build passed;
- 12 migrations, the seed and 6 SQL contracts parsed;
- 60 capture, 30 auto-tag, 24 assistant and 49 router contracts validated
  without calling a model.

## Real-data AI gate

The production AI policy remains `sample_only`. Google’s Gemini API terms
effective 23 March 2026 state that unpaid-service inputs and outputs may be used
to improve products and may be reviewed by humans, and explicitly say not to
submit sensitive, confidential or personal information. Artha must therefore
keep real financial text out of unpaid Gemini requests.

Private-data AI can be approved only after the Gemini Cloud project has an
active billing account (paid-service data terms) and the owner explicitly
enables that mode. Manual entry remains the free private-data path.

Sources:

- [Gemini API Additional Terms](https://ai.google.dev/gemini-api/terms)
- [Gemini Developer API pricing and data-use matrix](https://ai.google.dev/gemini-api/docs/pricing)

## Daily-use release implementation

- bounded database search covers description, category, note and either
  transfer account across the complete owner ledger without downloading every
  history page;
- normal history uses stable keyset pagination with an explicit **Load older
  activity** action and no fixed ledger-row cap;
- Quick Add offers **View transaction**, and every transaction row opens a
  detail surface;
- correction uses one atomic audited void-and-replacement operation; logical
  transfers remain paired and exact retries replay safely;
- removal requires a reason, preserves audit history and removes the logical
  activity from totals;
- existing participants can record repayments, with payer/payee direction
  derived atomically from the canonical database balance, exact retry replay,
  and settlements excluded from spending and income;
- posted repayments and statement-balance corrections remain visible and
  searchable as distinct read-only ledger movements;
- modal focus, Escape, Tab wrapping, page-scroll locking and focus restoration
  are covered by shared behavior;
- AI/privacy messaging now leads with one plain-language status and keeps
  provider details collapsed.

## Local evidence collected so far

| Check | Evidence | Result |
| --- | --- | --- |
| API transaction/settlement routes | focused production route suite, including database search and atomic settlement projection | PASS; 44 tests |
| Daily-use database behavior | fresh local Supabase reset followed by `supabase/tests/007_daily_use_transactions.sql` | PASS; transaction rolled back |
| Focused web behavior | Quick Add, Transactions, Shared and Settings suites | PASS |
| Responsive visual review | 390×844 dark Transactions/Shared and 1440×900 light Transactions/Settings | PASS; no horizontal overflow; inspected flows had no app errors |
| Dialog safety | correction and repayment dialogs | PASS; initial focus, scroll lock and mobile fit verified |
| Complete repository gate | ESLint, TypeScript, Ruff, strict mypy, Vitest, Pytest, PWA build, SQL parse and keyless AI contracts | PASS; 221 web, 286 API, 60 capture, 30 tag, 24 assistant and 49 router cases |
| Documentation and patch hygiene | local Markdown links and whitespace | PASS; 116 local links, clean diff check |

The database runtime was also linted at error level with no schema findings.

## Remaining publication evidence

- reviewed PR, main CI/CodeQL and merge;
- exact-project production migration plus rollback-safe SQL contract;
- exact-SHA Vercel deployments and signed-in final-domain acceptance.
