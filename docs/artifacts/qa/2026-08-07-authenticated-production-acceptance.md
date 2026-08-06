# Authenticated production acceptance

Date: 7 August 2026

Scope: final-domain acceptance using a disposable fictional identity and only
fictional names, accounts, balances and transactions. No credentials, email
links, tokens, backup contents or production identifiers are stored here.

## Release under test

- Web: <https://artha-web-one.vercel.app>
- API health: <https://artha-api-mu.vercel.app/health>
- Final production merge: `0376b60`
- Release PRs: #16 (Gemini, recovery and telemetry), #17 (live dashboard fixes),
  #18 (accessible mobile chart layout)

## Product journey results

| Journey | Result | Evidence |
| --- | --- | --- |
| New user authentication | Pass | Real production magic-link request and same-browser callback reached onboarding |
| Returning authentication | Pass | Sign-out followed by a new link restored the existing ledger without repeating onboarding |
| Session persistence | Pass | Navigating away and loading the app again restored the authenticated ledger |
| Onboarding | Pass | Two bank accounts, one credit card, opening balances and one household participant saved atomically |
| Backdated shared expense | Pass | ₹1,840 groceries from HDFC, dated three days earlier, split equally |
| Indian shorthand income | Pass | `25k` became ₹25,000 income in ICICI on yesterday's date |
| Self transfer | Pass | `self transfer 25k ICICI QA -> HDFC QA` produced one ₹25,000 transfer with ordered accounts and no income/spend change |
| Credit-card expense | Pass | ₹2,500 dinner selected the configured card and equal participant split |
| Transaction history | Pass | All/spend/income/transfer/shared counts were 4/2/1/1/2 before the final QA transaction |
| Account filter | Pass | HDFC=2, ICICI=2 and card=1; salary search returned one result |
| Shared ledger | Pass | Full paid amount, personal share and per-person receivable reconciled |
| Gemini capture | Pass | Production drafts grounded amount, date, account, category, participant and transfer direction |
| Gemini assistant | Pass | Provider reported `gemini-3.5-flash-lite`; available-balance metric and monthly-spend chart matched ledger totals |
| Encrypted export | Pass | Short/mismatched passphrase validation worked; valid client-side encryption produced a download success state |
| Encrypted restore | Pending | Must be exercised against a second fresh/empty production household |

## Defects found and closed during production QA

1. The Home monthly chart updated only after reload. PR #17 now updates the
   current month immediately after confirmed income/expense transactions.
2. Per-participant shared balance cards updated only after reload. PR #17 now
   updates them with the same confirmed transaction.
3. The chart grid widened Home at 320 CSS px. PR #17 added shrink-safe grid
   items; PR #18 moved the accessible data table into a clipped semantic wrapper.

The fixes are covered by regression tests for shared expense, income, transfer,
monthly chart and member-balance state.

## Responsive and theme acceptance

All primary pages were loaded from production and measured against the CSS
viewport, not the outer browser window.

| Page | 320 px | 390 px | 1440 px |
| --- | --- | --- | --- |
| Home | Pass | Pass | Pass |
| Transactions | Pass | Pass | Pass |
| Quick Add | Pass | Pass | Pass |
| Shared | Pass | Pass | Pass |
| Assistant | Pass | Pass | Pass |
| Settings / recovery | Pass | Pass | Pass |

Every row had `scrollWidth == innerWidth`. System, light and dark theme controls
changed the document color scheme correctly. Home passed visual review at
390 px dark and 1440 px dark; Settings passed explicit dark-state inspection.

## Automated and platform gates

```text
Web: 16 files, 103 tests passed
API: 122 tests passed
Quality: ESLint, TypeScript, Ruff and strict mypy passed
Build: production PWA passed
Database: 8 migrations, seed and 4 SQL contract files parsed
AI contracts: 50 capture, 30 auto-tag and 24 assistant cases valid
Hosted Gemini: 50/50 capture, 30/30 auto-tag and 24/24 assistant on fictional data
Vercel: web and API preview plus production deployments ready
Public smoke: web routes and API health returned 200
Telemetry: Analytics and Speed Insights bundle endpoints present
```

GitHub did not create the protected Web/API/SQL workflow runs for PRs #16-#18.
The repository-owner merge override was used after the equivalent full local
gate and both Vercel preview checks passed. This provider/CI issue remains
visible rather than being represented as a successful GitHub Actions run.

## Remaining real-data release guard

- Prove two independent owners cannot read or write each other's households.
- Restore the encrypted backup into the second identity's fresh/empty household
  and reconcile balances, transactions, transfers, splits and audit facts.
- Record sanitized authenticated cold/warm latency and log-redaction evidence.
- Repeat setup with the owner's complete four-bank/multiple-card configuration.

Until those items pass, the deployment is suitable for continued fictional
private-pilot testing, not real family-finance data.
