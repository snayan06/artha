# V1 account activity filter

Date: 5 August 2026
Status: implemented and verified locally

## User outcome

The transaction ledger can be narrowed to one bank account, card, wallet or
cash account. This makes a household with four banks and several cards usable
without mixing every movement into one list.

Transfers appear under both their source and destination account. Searching an
account name also matches either side of a transfer, while the displayed net
cashflow remains zero for internal transfers.

## Responsive behavior

- On mobile, transaction-type chips scroll horizontally and the account picker
  occupies its own full-width row.
- On wider screens, the picker sits beside the type filters.
- The picker is explicitly labelled for screen readers and keeps a 44-pixel
  minimum touch target.

## Code and tests

- UI: `apps/web/src/pages/TransactionsPage.tsx`
- Regression tests: `apps/web/src/pages/TransactionsPage.test.tsx`

The tests prove that a destination account finds its transfer and that account
names are included in text search. Adding, renaming and archiving accounts after
onboarding remains a separate settings feature in Sprint 2.
