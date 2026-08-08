# Artha V1 QA scenario matrix

Updated: 8 August 2026
Scope: local V1 source, fictional demo data, final-domain fictional acceptance,
and the remaining real-data release backlog

## How to read this matrix

- **Automated** runs in `make check` and GitHub CI.
- **Manual local** was exercised against the local PWA at the named viewport.
- **Production pending** requires the final Supabase and hosting accounts and cannot
  be declared green from the local demo.
- Every scenario must use fictional data. Real financial data is prohibited until
  the production security and recovery rows are green.

## Setup, accounts, and cards

| ID | Scenario | Expected result | Coverage |
| --- | --- | --- | --- |
| SET-01 | First run with one bank account | Opening balance is stored in integer paise | Automated |
| SET-02 | Four bank/cash/wallet accounts | All accounts are created atomically with independent balances | Automated API contract |
| SET-03 | Multiple credit cards | Outstanding is negative; limit and statement/due days are preserved | Automated |
| SET-04 | Credit-card outstanding exceeds limit | Setup is rejected before save | Automated UI/API |
| SET-05 | Credit-card statement or due day is 0, 32, or fractional | Setup is rejected | Automated API; UI validation covered |
| SET-06 | Duplicate account names with case/whitespace differences | Entire setup is rejected with no partial accounts | Automated UI/API |
| SET-07 | Duplicate family member names | Entire setup is rejected with no partial members/accounts | Automated |
| SET-08 | Empty account name or missing balance | User remains on setup and receives an accessible error | Automated UI validation |
| SET-09 | `Infinity`, `NaN`, or browser-unsafe amount | Value is rejected at the browser money boundary | Automated |
| SET-10 | Fictional demo selected | Demo seed is explicit, replay-safe, and never duplicates rows | Automated |

## Capture, dates, and categorization

| ID | Scenario | Expected result | Coverage |
| --- | --- | --- | --- |
| CAP-01 | `Paid 1840 for groceries from HDFC UPI` | Expense draft has ₹1,840, account, description, and category | Automated |
| CAP-02 | `Rs. 1,234.56` | Decimal converts exactly to 123,456 paise | Automated |
| CAP-03 | No amount | Parser rejects the message and nothing is saved | Automated |
| CAP-04 | Account omitted | First account is proposed with a visible review warning | Automated |
| CAP-05 | Unknown category | Draft is marked for review; confirmation remains explicit | Automated |
| CAP-06 | Today/yesterday/day-before-yesterday | Local calendar day maps correctly without UTC drift | Automated |
| CAP-07 | `3 days ago` and `3 days back` | Historical date is parsed relative to the caller timezone | Automated |
| CAP-08 | ISO date `YYYY-MM-DD` | Exact date is retained | Automated |
| CAP-09 | `31 Dec` entered on 2 January | Most recent past occurrence is used (previous year) | Automated |
| CAP-10 | Ambiguous numeric or impossible date | Parser rejects it and requests an unambiguous date | Automated |
| CAP-11 | Invalid IANA timezone | API returns validation error, not a silently shifted date | Automated |
| CAP-12 | Production capture provider or API is unavailable | Exact source text is preserved, an unsaved manual review form opens, and no language-parser guess is substituted | Automated; final-domain acceptance pending |
| CAP-13 | API validation error | Error is shown and no draft is fabricated or saved | Automated |
| CAP-14 | Merchant rule matches in the local/demo repository | The stored household rule is used without changing the production web capture contract | Automated; production learning is planned |
| CAP-15 | Learned merchant rule | It affects future drafts only and does not rewrite history | Automated |
| CAP-16 | Manual recovery type correction | Expense, Income and Transfer use direction-valid server-owned categories/accounts and remain unsaved until confirmation | Automated; production verified on `c4ae0dc` |
| CAP-17 | Account-context load fails | Exact text and any safe draft fields survive retry; confirmation stays disabled with an accessible reason | Automated; final-domain acceptance pending |

## Confirmation and ledger invariants

| ID | Scenario | Expected result | Coverage |
| --- | --- | --- | --- |
| LED-01 | Parse without confirmation | Transaction count and balances remain unchanged | Automated UI/API |
| LED-02 | Rapid double confirmation | UI permits one pending write only | Automated |
| LED-03 | Same idempotency key replay | Same transaction is returned; no duplicate ledger movement | Automated |
| LED-04 | Concurrent same-key requests | At most one transaction is stored | Automated |
| LED-05 | Same key reused with changed payload | API returns conflict and keeps original transaction | Automated |
| LED-06 | Income | Account and income increase; spending does not | Automated |
| LED-07 | Expense | Full cash amount leaves account; personal share drives spending | Automated |
| LED-08 | Bank-to-cash transfer | Total balance, income, and spending are unchanged | Automated |
| LED-09 | Bank-to-credit-card payment | Cash and card outstanding move; no second expense is created | Automated |
| LED-10 | Same source/destination transfer | Draft is rejected | Automated |
| LED-11 | Unknown/archived account reference | Confirmation returns not found and writes nothing | Automated |
| LED-12 | Edit amount/split | Entries and derived balances are rebuilt from the corrected draft | Automated |
| LED-13 | Soft delete | Transaction disappears and all derived effects reverse | Automated |
| LED-14 | Very large safe paise value | BigInt storage round-trips without truncation | Automated |
| LED-15 | More than 10,000 rows | Dashboard/shared aggregates are complete; recent list stays capped | Automated |

## Family splits and settlements

| ID | Scenario | Expected result | Coverage |
| --- | --- | --- | --- |
| SHR-01 | Equal split with one family member | Cash moves in full; personal/member shares are separate | Automated |
| SHR-02 | Equal split with two family members | All shares add exactly to the transaction total | Automated |
| SHR-03 | Odd-paise multi-member split | Remainder is deterministic and no paise is lost | Automated |
| SHR-04 | Equal split without a recognized member | Draft is rejected for review | Automated |
| SHR-05 | Duplicate member in splits | Draft is rejected | Automated |
| SHR-06 | Unknown/archived member reference | Confirmation returns not found and writes nothing | Automated |
| SHR-07 | Family member paid the expense | User account does not move; user share becomes payable | Automated |
| SHR-08 | Member reimburses the user | Balance decreases; receipt is not counted as income | Automated |
| SHR-09 | User pays a member settlement | Balance clears; payment is not counted as spending | Automated ledger semantics |
| SHR-10 | Multiple members owe/opposite directions | Per-member balances remain independent | Automated |

## Authentication, assistant, and security

| ID | Scenario | Expected result | Coverage |
| --- | --- | --- | --- |
| SEC-01 | Missing production bearer token | API rejects request | Automated |
| SEC-02 | Expired/wrong audience/wrong issuer token | API rejects request | Automated |
| SEC-03 | Disallowed symmetric JWT or service-role token | API rejects without trusting it | Automated |
| SEC-04 | JWKS key rotation | Unknown key triggers a controlled JWKS refresh | Automated |
| SEC-05 | JWKS provider outage | API returns service unavailable, never unauthenticated demo data | Automated |
| SEC-06 | Assistant provider disabled | API returns a sanitized unavailable response; the UI retains the exact question and renders no fabricated widgets | Automated |
| SEC-07 | Model returns extra fields/HTML/SQL-like payload | Payload is rejected or stripped; no HTML is rendered | Automated |
| SEC-08 | Model invents a category | Suggestion is rejected outside the allow-list | Automated |
| SEC-09 | Assistant question | Transaction rows are unchanged before/after | Automated |
| SEC-10 | Provider status | API key is never serialized to the browser | Automated |
| SEC-11 | Two authenticated households | Cross-household reads/writes are denied by RLS | Production pending on fresh project |
| SEC-12 | Gemini data-use notice | The fictional-only boundary is visible and telemetry contains no financial content | Automated; real-data privacy approval pending |

## UX, responsive, and operational behavior

| ID | Scenario | Expected result | Coverage |
| --- | --- | --- | --- |
| UX-01 | Text capture and form-first capture | Both reach the same review-before-write flow | Automated/manual local |
| UX-02 | Zero or negative manual amount | Confirm stays disabled | Automated |
| UX-03 | 320 px viewport | Cards, form, and bottom navigation fit without horizontal overflow | Manual local |
| UX-04 | 390 px viewport | Primary mobile layout fits without horizontal overflow | Manual local; production verified on all six primary routes |
| UX-05 | Desktop viewport | Content width, charts, and navigation remain readable | Manual local |
| UX-06 | Light, dark, and system themes | Controls remain visible and preference persists | Automated/manual local; production dark/system verified |
| UX-07 | Capture API unavailable | Exact text is retained, manual review explains the error, and no silent save occurs | Automated; authenticated final-domain acceptance pending |
| UX-08 | PWA production build | Manifest, service worker, and precache are generated | Automated build |
| OPS-01 | Web/API restart from renamed folder | Root `.env` is loaded and both documented URLs become healthy | Automated configuration plus local smoke |
| OPS-02 | Final-domain login/refresh/sign-out | Session survives refresh and signs out cleanly | Production verified |
| OPS-03 | Export, restore, and recovery drill | Restored totals match source and secrets remain protected | Production pending |
| OPS-04 | Full browser process close and reopen | The authenticated session returns without repeating onboarding | Production pending |
| OPS-05 | Sanitized logs and authenticated latency | Browser/API logs expose no token or financial payload; cold/warm timings contain no request content | Production pending |

## Release commands

```bash
make check
git diff --check
```

For a production release, additionally execute every **Production pending** row
against the final URLs and record sanitized evidence in this directory.
