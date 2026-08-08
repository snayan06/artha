# Capture-hardening production acceptance

Date: 8 August 2026

Scope: final-domain verification after V1 capture-hardening PR #21. All names,
accounts, balances and transactions used in this exercise were fictional. No
credentials, tokens, sign-in links, backup contents or private identifiers are
recorded here.

## Release under test

- Merge: `c4ae0dcaf78f3d8b3458d49b257cff37643bd0b2`
- Pull request: [#21](https://github.com/snayan06/artha/pull/21)
- Main CI: [31271421128](https://github.com/snayan06/artha/actions/runs/31271421128)
- CodeQL: [31271421107](https://github.com/snayan06/artha/actions/runs/31271421107)
- Web deployment: GitHub deployment `5811366329`, successful
- API deployment: GitHub deployment `5811363817`, successful
- Web: <https://artha-web-one.vercel.app>
- API health: <https://artha-api-mu.vercel.app/health>

## Platform results

| Gate | Result | Evidence |
| --- | --- | --- |
| Merge identity | Pass | PR #21 is merged and `origin/main` resolves to `c4ae0dc` |
| Main CI | Pass | Web, API and Supabase SQL jobs completed successfully |
| CodeQL | Pass | JavaScript/TypeScript and Python analyses completed successfully |
| Vercel production | Pass | Web and API deployments for the merge commit completed successfully |
| Public smoke | Pass | Web root and API health both returned HTTP 200; health reported `v1-production` |

## Authenticated fictional journey

| Journey | Result | Evidence |
| --- | --- | --- |
| Returning session | Pass | Opening the production app in the established QA browser restored the existing server-owned ledger without onboarding |
| Six core routes | Pass | Home, Transactions, Shared, Assistant, Settings and Quick Add loaded without an application error |
| Gemini expense | Pass | `Paid 123 for QA deployment coffee from HDFC QA today` produced an unsaved ₹123 Expense draft, grounded the account and category, and required explicit confirmation |
| Confirmed write | Pass | Confirmation produced the success screen; available balance decreased by ₹123, spending increased by ₹123 and the recent activity row appeared |
| Gemini income | Pass | `Received 25k QA salary today in ICICI QA` produced an unsaved ₹25,000 Income draft with the selected account |
| Gemini transfer | Pass | `self transfer 25k HDFC QA -> ICICI QA` produced an unsaved ₹25,000 Transfer draft with ordered source/destination accounts |
| Manual recovery | Pass | The exact source sentence remained visible; Expense, Income and Transfer forms each rendered with server-owned account/category controls and no write |
| Read-only assistant | Pass | `What is my available balance?` returned the exact dashboard balance and matching monthly spend/income through `gemini-3.5-flash-lite` |
| Transaction filters | Pass | Transfers, Income, Shared, Spend and search returned only their expected fictional rows and counts |
| Shared reconciliation | Pass | Full amount paid, personal share and member receivable reconciled across three shared expenses |
| Encrypted export | Pass | A valid local-only passphrase produced the encrypted-download success state; the passphrase was not recorded |
| Mobile layout | Pass | All six primary routes had `scrollWidth == innerWidth` at 390 × 844 CSS px |
| Theme | Pass | System → Light → Dark switching worked; the 390 px dark Settings view had no horizontal overflow; the preference was returned to System |

The unsaved income, transfer and manual-recovery drafts were intentionally
discarded. Only the single ₹123 fictional QA expense was confirmed.

## Automated gate for the same source

```text
Web: 18 files, 170 tests passed
API: 223 tests passed
Quality: ESLint, TypeScript, Ruff and strict mypy passed
Build: production PWA passed
Database: 8 migrations, seed and 4 SQL contracts parsed
AI contracts: 50 capture, 30 auto-tag and 24 assistant cases valid
Documentation links: 95 local links across 58 Markdown files
```

## Remaining real-data release guards

- Prove two independent production owners cannot read or write each other's
  households.
- Restore the encrypted backup into a fresh/empty second household and reconcile
  transactions, balances, transfers, splits and audit facts.
- Exercise a real provider-unavailable event on the final domain and confirm the
  exact submitted text/question survives without a fabricated result or write.
- Verify persistence across a full browser-process close and reopen.
- Record sanitized authenticated latency and log-redaction evidence.
- Approve the provider/privacy configuration for real family-finance content and
  rerun the hosted fictional model gates for this exact release.

Until these rows pass, the deployment is ready for the user's own **fictional
manual testing**, not real family-finance data.
