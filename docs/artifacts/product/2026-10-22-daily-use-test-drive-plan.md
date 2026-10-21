# Daily-use test-drive plan

Date: 22 October 2026

## Decision

Artha will begin as a forward-looking private ledger from one explicit opening
snapshot. Historical statement import is useful later, but it is not required
to start dependable daily tracking.

The user chooses a start date and time, records the exact posted balance for
every active money account and the current outstanding balance for every credit
card, and records only activity after that cutoff. Artha is reconciled against
real balances during the pilot and against statements at the end of each card
or bank cycle.

## Release outcome

The test-drive release is complete when one real owner can:

1. sign in and return without repeating onboarding;
2. create a dated opening snapshot for all accounts and cards;
3. record expenses, income, transfers, refunds and shared expenses after the
   cutoff;
4. record a card purchase once, on its purchase date;
5. record a card-bill payment as a bank-to-card transfer rather than another
   expense;
6. correct or remove a mistaken entry with an audit trail;
7. compare Artha's calculated balance with the actual account/card balance;
8. understand and resolve any difference before continuing; and
9. export an encrypted backup and restore it successfully.

## Information required from the owner

- start date, time and timezone;
- account nickname, kind, currency and exact posted balance at the cutoff;
- card nickname, current outstanding, credit limit, statement day and due day;
- any pending or unposted entries that cross the cutoff;
- optional household participants used for shared expenses.

Artha never needs bank-login passwords, OTPs, PINs, CVVs, full account numbers
or full card numbers.

## Money rules for the pilot

| Event | Account effect | Spending effect |
| --- | --- | --- |
| Bank/cash purchase | Money account decreases | Expense on purchase date |
| Credit-card purchase | Card outstanding increases | Expense on purchase date |
| Card-bill payment | Bank decreases; card outstanding decreases | No new expense |
| Own-account transfer | One account decreases; another increases | No expense or income |
| Refund | Receiving account/card improves | Reverses or reduces spending |
| Investment contribution/redemption | Account balance changes | Not household spending/salary |
| Balance reconciliation | Audited adjustment after review | Not expense or income |

## Ordered implementation and acceptance

### Gate 0 - restore access

- Resume or restore the exact Supabase production project. Its configured
  hostname currently returns DNS `NXDOMAIN`, so no magic link can be sent.
- If the original project reference returns, keep existing Vercel variables.
  If the project was replaced, apply every migration, update both deployments'
  Supabase variables and configure the exact site/redirect URLs.
- Deploy the safe authentication error classification that distinguishes a
  temporary outage and rate limit without leaking provider details.
- Pass new-user link, returning-user link, reload, sign-out and browser-reopen
  acceptance.

### Gate 1 - opening snapshot

- Make the cutoff date/time and balance meaning explicit during onboarding.
- Clarify that balances must include posted activity through the cutoff and that
  new entries start strictly after it.
- Keep unfinished onboarding recoverable and allow accounts/cards to be edited
  later.
- Show an opening-position review: assets, card liabilities and net position.

### Gate 2 - daily capture

- Manually accept Expense, Income, Transfer, Refund and shared-expense flows.
- Verify Indian shorthand, account/card nicknames and backdated dates through
  the review-before-save path.
- Verify card purchases increase outstanding and card payments reduce it without
  increasing spending.
- Verify correction, removal, search and source-linked transaction detail.

### Gate 3 - reconciliation and recovery

- Run a short daily comparison during the first week.
- At cycle end, compare actual versus calculated balance for every account and
  card, explain the difference, and add only an explicit audited adjustment.
- Download an encrypted backup and restore it into a fresh empty household.
- Repeat owner-isolation and provider-unavailable recovery tests.

### Gate 4 - measured pilot

- Use Artha for four weeks.
- Track capture coverage, correction rate, unresolved items and reconciliation
  differences without recording financial text in telemetry.
- Consider the pilot successful when at least 90% of activity is captured and
  every remaining difference is explainable.

## Deliberately after the test drive

- Historical statement import, deduplication and cross-source event matching.
- The richer cash-versus-purchase analysis demonstrated by the private Spending
  Explorer.
- Member login/invitations and member-paid expense flows.
- Investments and valuation tracking.
- Voice capture. Voice must reuse the same editable, unsaved draft and explicit
  confirmation path; it never writes directly to the ledger.
- Agentic analysis and scenarios beyond the current bounded read-only assistant.

## Immediate pending list

1. **User action:** resume/restore `artha-production` in Supabase.
2. **Code:** safe authentication-outage messaging is implemented and tested;
   deploy it after Supabase is restored, then retest sign-in.
3. **Product:** reload-safe opening-snapshot guidance and exact-paise review are
   implemented and tested; deploy and accept them with the auth fix.
4. **QA:** complete authenticated fictional daily-capture and card-payment
   scenarios on the final domain.
5. **User + QA:** enter the approved opening snapshot and begin the controlled
   personal pilot.
