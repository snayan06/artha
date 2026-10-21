# Real-statement product validation

Date: 22 October 2026

## Purpose

Validate Artha's ledger and capture model against a private, local-only sample
of real bank and credit-card activity before importing or entering real finance
data at scale.

The source set covered three bank accounts, two credit-card statement streams,
overlapping statement periods and an existing local reconciliation workbook.
Raw exports, names, merchants, account identifiers, balances and transaction
amounts are intentionally excluded from this repository artifact. The source
files were inspected locally and were not uploaded, committed or sent to an
LLM.

## What the evidence changes

### 1. Cash movement is not the same as spending

The sample contains ordinary purchases alongside own-account transfers,
credit-card bill payments, investment contributions and proceeds, property or
capital-asset payments, refunds, interest, fees and uncertain person-to-person
payments.

Artha must preserve both views:

- **Cash movement:** what changed each account balance.
- **Economic activity:** what was actually spent, earned, invested, refunded or
  transferred.

A dashboard that derives spending directly from bank debits will materially
overstate expenses.

### 2. One event can appear in several sources

A card purchase can later appear as a card statement balance, a payment through
a bill-payment platform and a bank debit. These are related records, not four
expenses. Rewards and refunds can introduce additional linked entries.

Artha needs an explicit `financial_event` relationship or equivalent link so a
purchase, settlement, refund and bank movement can be reconciled without
rewriting source evidence.

### 3. Statement coverage is partial by default

Bank periods, card billing cycles and export cut-off dates do not align. Missing
days or an absent card statement mean **unknown coverage**, never zero activity.

Every import batch should record:

- source account and source type;
- covered-from and covered-through dates;
- statement date and billing due date where relevant;
- whether purchase detail, settlement detail or both are present;
- known gaps and overlap with earlier imports.

### 4. Ambiguous payments need a review inbox

Many person-to-person payments expose only a name or abbreviated narration.
Their purpose cannot be safely inferred as food, reimbursement, family support,
loan, rent or transfer.

The product should surface a compact review queue with grounded suggestions,
not silently force a category. A confirmed answer may create a prospective
household rule, but must not retroactively rewrite unrelated history.

### 5. Reconciliation and provenance are product features

For every imported row Artha should retain private, owner-scoped provenance:

- source document and import batch identifiers;
- source page or row reference;
- transaction date and posting/value date;
- raw normalized narration and canonical merchant/payee;
- source fingerprint and duplicate decision;
- proposed classification, confirmed classification and review status;
- links to a matching transfer, card payment, refund or settlement.

The user should be able to trace a balance or category total back to its source
without exposing raw documents to the assistant.

### 6. Fees and interest deserve first-class visibility

Card fees, interest and tax are neither purchases nor bill payments. They should
be separate categories, appear in due-date/reconciliation views and support a
clear avoidable-charge insight without becoming financial advice.

### 7. Investments remain a separate product domain

Investment funding and redemption cash flows should affect account balances but
not household spending or salary. Holdings, realised gains/losses, dividends,
tax lots and valuation timestamps require the separately planned Investments
domain; they should not be compressed into expense categories.

## Required product slice before private import

1. Browser/local statement parsing and a review-only staging table.
2. Account, date, amount and direction validation using integer paise.
3. Source coverage and overlap detection.
4. Cross-source matching for own transfers, card settlements and refunds.
5. Explicit handling for investments, asset purchases, fees and uncertain
   receipts/payments.
6. Household-scoped fingerprints and atomic, idempotent confirmation.
7. A reconciliation summary showing opening balance + movements = closing
   balance for each account.
8. A review inbox for unclassified or weakly matched rows.
9. Encrypted export/restore coverage for imports, provenance and links.

## Voice capture epic - after the ledger/import gate

Voice is a capture surface, not a new accounting path. A recording must produce
the same unsaved, validated draft as typed input and must never write directly
to the ledger.

### User flow

1. Tap and hold, or tap once, to record from the unified composer.
2. Show the transcript before interpretation and allow immediate editing.
3. Parse through the same grounded household context and strict draft schema as
   typed capture.
4. Ask at most one missing-field question at a time with account/member/category
   choice chips.
5. Show the complete review card and require explicit confirmation.

### Voice-specific requirements

- English, Hinglish and Indian-number phrases such as `25k`, `one lakh` and
  `twelve hundred`.
- Account/card nicknames, transfers, shared expenses, backdated dates and
  corrections such as “no, make that twelve hundred”.
- Visible listening, processing, permission-denied, offline and retry states.
- Audio is not retained by default. Cloud transcription requires explicit data
  disclosure and owner consent; on-device transcription is preferred where it
  is sufficiently accurate.
- The transcript, not raw audio, is the input to the existing draft parser.
- No model-authored ledger IDs, calculations or confirmation actions.

### Voice release gate

- Zero direct writes from audio or transcript.
- 100% exact amount/account/date/type accuracy for accepted high-confidence
  drafts in the critical evaluation set.
- Zero false-ready transfers, card payments, settlements or multi-amount input.
- Tested noisy-room, Indian-accent, code-switching, interruption, correction,
  permission-denied and offline cases.
- Transcript and audio excluded from analytics, error reports and Git fixtures.
- Mobile and desktop accessibility, keyboard fallback and screen-reader status
  announcements pass.

## Recommended sequence

1. Finalise statement-driven ledger/import contracts.
2. Build local staging, matching, reconciliation and review.
3. Test with fictional fixtures plus a private local acceptance set.
4. Complete the personal daily-use pilot and close the remaining release gates.
5. Build and evaluate Voice Capture on the proven typed-draft path.

