# Unified entry production release

Date: 9 August 2026  
Production commit: `e32b5b60b5575be9019d9253381ed4400be7a097`  
Status: deployed and ready for signed-in user acceptance

## User-visible outcome

Artha now has one AI entry experience across Home and Quick Add:

- A transaction sentence opens an unsaved review draft. It never writes to the
  ledger until the user explicitly confirms it.
- A ledger question opens Ask Artha and returns read-only, server-grounded UI.
- Ambiguous or mixed text stays on the page and asks the user to choose **Add as
  transaction** or **Ask about my ledger**.
- Unsupported real-money commands and settlement instructions are not converted
  into ledger entries.
- Enter submits, Shift+Enter adds a new line and text entered through an IME is
  not accidentally submitted.
- Clarification, progress and error messages are accessible and preserve the
  user's exact text for retry.
- Merchant, platform, category, subcategory, context and tags use
  case-insensitive matching and one canonical stored display label.

PR [#23](https://github.com/snayan06/artha/pull/23) and PR
[#24](https://github.com/snayan06/artha/pull/24) are merged. PR #24's intent
router is part of the combined production release rather than a separate
deployment.

## Safety boundaries

- The router receives text only. It has no ledger read or write access.
- Capture creates an unsaved proposal. FastAPI validates grounded IDs, integer
  paise, dates, splits and metadata before the review can be confirmed.
- Ask Artha remains read-only and renders allow-listed React components from
  server-calculated ledger bundles; it does not render model-authored HTML.
- Gemini does not connect directly to Supabase and cannot move money.
- Raw chain-of-thought is not shown. The UI may show truthful progress and a
  concise user-facing explanation, never hidden model reasoning.

## Verification evidence

Fresh combined release gate:

- Web: 20 test files, 206 tests passed.
- API: 275 tests passed.
- ESLint, TypeScript, Ruff and strict mypy passed.
- Production PWA build passed.
- Eight migrations, seed and four SQL contracts parsed.
- AI contracts: 60 capture, 30 auto-tag, 24 assistant and 49 intent-router
  cases validated.
- Hosted intent router on `gemini-3.5-flash-lite`: 49/49 available, 48/49 exact
  (98.0%), 100% safety accuracy and zero false captures. The single miss chose
  the safe read-only assistant instead of clarification; it did not create a
  transaction.
- Independent final review found no remaining Critical or Important issue.

GitHub release evidence:

- `main`: `e32b5b60b5575be9019d9253381ed4400be7a097`
- [CI run 31278245585](https://github.com/snayan06/artha/actions/runs/31278245585): passed
- [CodeQL run 31278245587](https://github.com/snayan06/artha/actions/runs/31278245587): passed for JavaScript/TypeScript and Python

Vercel release evidence:

- Web deployment: `dpl_3N9eY6NL57ZGjbhzqbwXA6FqvGsv`, Ready
- API deployment: `dpl_4cULJbxRhDrSQHojiYKYAS4Lhw6A`, Ready in Mumbai (`bom1`)
- [Production app](https://artha-web-one.vercel.app/)
- [API health](https://artha-api-mu.vercel.app/health)

## Manual browser QA completed

The exact merged code was exercised with an isolated fictional ledger and the
configured Gemini provider at 390 px mobile and 1440 px desktop widths:

1. `Paid 850 for dinner from HDFC UPI yesterday` routed to Quick Add.
2. Gemini produced an unsaved ₹850 Expense review with Dinner, Food & Dining,
   HDFC UPI and yesterday's date.
3. Explicit confirmation saved the fictional transaction and returned Home.
4. `Show my spending trend for the last three months` routed to Ask Artha and
   returned the safe cash-flow UI.
5. `Add this and tell me whether I overspent: paid 700 for dinner` stayed on
   Home and showed the two explicit destination choices.
6. Both widths had no horizontal overflow and the successful flow produced no
   app-owned console error.

The public production login page also passed a 390 px smoke check with no
horizontal overflow or app console error. Production routes and API health are
publicly reachable, and the intent endpoint correctly rejects anonymous access.

## What the user should test

Open [Artha production](https://artha-web-one.vercel.app/), sign in with the
existing personal test identity and use fictional data for this acceptance:

1. From Home, enter `Paid 850 for dinner from HDFC UPI yesterday` and confirm
   that Quick Add opens an unsaved review.
2. Verify merchant/category/account/date metadata, then confirm only if the
   review is correct.
3. From Home, ask `Show my spending trend for the last three months` and verify
   it opens Ask Artha without creating a transaction.
4. Enter the mixed sentence from the manual QA and verify the two destination
   choices appear.
5. Refresh, sign out and sign back in; confirm onboarding is not repeated.

This signed-in production acceptance is deliberately left to the user because
no password, magic-link token or private session is stored in the repository or
test runner.

## Remaining release guards before real financial data

- Complete two-owner/two-household isolation with a second fictional identity.
- Close and reopen the complete browser process to confirm session persistence.
- Restore the encrypted sample backup into a fresh/empty household and compare
  totals.
- Exercise real provider-unavailable recovery on the final domain.
- Record sanitized production logs and authenticated cold/warm latency.
- Approve the provider/privacy configuration for real family-finance text.
- Rerun the combined 60-case hosted capture benchmark after the metadata fixes.

## Next sprint plan

1. **Accounts & family:** owner-only settings, add/rename/archive accounts and
   cards, audited balance corrections and participant maintenance.
2. **Family access:** invitation lifecycle, owner-only RLS hardening and a
   minimal **Shared with me** view that never exposes private balances.
3. **Private AI learning:** RLS-backed interaction/review history, opt-out,
   export/delete controls, resumable eval runs and sanitized dataset promotion.
4. **Metadata analytics:** household tags and aliases, merchant/platform/category
   breakdowns and canonical database-calculated Ask Artha bundles.
5. **Investments planning:** a future Investments tab for mutual funds and
   stocks, starting with manual entry/CSV import and timestamped valuations.
6. **Agentic assistant planning:** a later bounded read-only multi-step analyst
   with deterministic evidence; no autonomous writes, payments or trading.

The ordered implementation and acceptance gates are maintained in the
[sprint board](../../SPRINT-BOARD.md).
