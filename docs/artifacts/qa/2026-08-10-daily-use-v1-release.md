# Daily-use V1 release evidence

Date: 10 August 2026
Status: published and accepted with disposable fictional data

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

## Release evidence

| Check | Evidence | Result |
| --- | --- | --- |
| API transaction/settlement routes | focused production route suite, including database search and atomic settlement projection | PASS; 44 tests |
| Daily-use database behavior | fresh local Supabase reset followed by `supabase/tests/007_daily_use_transactions.sql` | PASS; transaction rolled back |
| Focused web behavior | Quick Add, Transactions, Shared and Settings suites | PASS |
| Responsive visual review | 390×844 dark Transactions/Shared and 1440×900 light Transactions/Settings | PASS; no horizontal overflow; inspected flows had no app errors |
| Dialog safety | correction and repayment dialogs | PASS; initial focus, scroll lock and mobile fit verified |
| Complete repository gate | ESLint, TypeScript, Ruff, strict mypy, Vitest, Pytest, PWA build, SQL parse and keyless AI contracts | PASS; 221 web, 288 API, 60 capture, 30 tag, 24 assistant and 49 router cases |
| Documentation and patch hygiene | local Markdown links and whitespace | PASS; 118 local links, clean diff check |

The database runtime was also linted at error level with no schema findings.

## Publication and production acceptance

| Check | Evidence | Result |
| --- | --- | --- |
| Feature publication | PR [#30](https://github.com/snayan06/artha/pull/30) merged as `1531968`; main [CI](https://github.com/snayan06/artha/actions/runs/31400743351) and [CodeQL](https://github.com/snayan06/artha/actions/runs/31400746074) | PASS |
| Browser-settlement wire fix | PR [#31](https://github.com/snayan06/artha/pull/31) merged as `7b3d78b`; main [CI](https://github.com/snayan06/artha/actions/runs/31402906215) and [CodeQL](https://github.com/snayan06/artha/actions/runs/31402906126) | PASS |
| Onboarding split-candidate fix | PR [#32](https://github.com/snayan06/artha/pull/32) merged as `cc7934c`; main [CI](https://github.com/snayan06/artha/actions/runs/31408304984) and [CodeQL](https://github.com/snayan06/artha/actions/runs/31408301066) | PASS |
| Production database | `20260810010000_transaction_correction_search_settlement.sql` applied to the exact project; six RPCs resolved; rollback-only SQL contract 007 passed | PASS; no test rows remained |
| Exact-SHA deployments | Vercel production web and API deployments for `cc7934c` | PASS |
| Signed-in final-domain journey | Password login, onboarding, mobile dashboard, manual confirmation, detail, correction, complete-ledger search, shared balance, repayment and read-only repayment history | PASS |
| AI-assisted journey | Gemini capture produced an unsaved grounded Zomato draft with category, account, date and merchant metadata; Ask Artha returned the exact database-backed balance widget | PASS with fictional data |
| Onboarding regression | Freshly hydrated Quick Add offered the participant but not the authenticated owner as a split candidate | PASS |
| Primary-route smoke | Home, Transactions, Shared, Assistant and Settings on the exact production build at 390 CSS px | PASS; no fatal state or horizontal overflow |
| Responsive check | Quick Add at 390×844 and 1440×900 CSS px | PASS; document width equalled viewport width |
| Test identity teardown | The disposable auth user, profile, household and ledger were removed; the final-owner protection trigger was restored and verified enabled | PASS |

## Daily-use boundary

The manual ledger, account/card maintenance, complete history, correction,
removal, splitting and repayment paths are ready for the owner's day-to-day
testing. AI was accepted only with fictional data. Real family-finance text must
remain out of Gemini until the private-data AI gate below is approved.

## Remaining real-data gates

- approve a paid/private AI configuration with an explicit owner control, or
  keep using manual entry for private financial text;
- repeat the encrypted restore through the final-domain UI into a fresh empty
  household;
- complete a second-identity/browser-process isolation and persistence drill;
- record sanitized provider-unavailable and cold/warm latency evidence.
