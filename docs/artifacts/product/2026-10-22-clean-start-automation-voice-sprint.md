# Clean start, assisted capture and Voice Capture sprint

Date: 22 October 2026  
Status: approved product plan; bulk balance snapshot is in implementation  
Scope: private personal use with friends/family split participants

## Outcome

Move Artha from a prototype ledger containing stale or incomplete entries to a
trustworthy daily-use ledger, then reduce repeated manual capture. The owner can
review every bank and card in one place, start from a deliberate dated snapshot
and add transactions through text or voice without any silent ledger writes.

## The three workflows must stay separate

1. **Update all balances** keeps transaction history and records only the
   differences as audited adjustments. This is for routine statement
   reconciliation.
2. **Start fresh** retires stale/incomplete activity from live totals after a
   mandatory encrypted backup, keeps the account/card roster, and creates one
   new dated balance snapshot. This is a deliberate reset, not ordinary
   reconciliation.
3. **Import missing activity** stages statement or alert rows for review,
   deduplication and explicit confirmation. It repairs history instead of
   changing a balance without explanation.

## Ordered sprint board

| ID | Priority | Epic | Deliverable | Acceptance gate |
| --- | --- | --- | --- | --- |
| CS-01 | P0 | Account/card inventory | One checklist for active banks, cash, wallets and cards; add/rename/edit card limit/statement/due dates; archive unused zero-balance accounts | The owner can explain every active account and card before setting balances |
| CS-02 | P0 | Bulk balance snapshot | One dated form for all posted bank balances and positive card outstanding amounts, followed by a single review and confirmation | Only changed balances create integer-paise audited adjustments; unchanged accounts are untouched |
| CS-03 | P0 | Safe **Start fresh** | Preview stale rows, create/download an encrypted backup, choose cutoff date, enter all target balances and confirm with an explicit destructive-warning phrase | One atomic, idempotent owner-only operation removes old rows from live totals, records the new snapshot and writes an audit event; no physical deletion occurs |
| CS-04 | P0 | Clean-start verification | Reopen the app, compare every displayed balance with source apps/statements and test card purchase plus card-bill transfer | Dashboard, accounts, search and assistant use only the new live period; the backup can still be previewed |
| IM-01 | P1 | Missing-activity inbox | Stage CSV/PDF/WhatsApp/bank-alert candidates locally or server-side under the approved privacy policy; show duplicates and missing fields | Nothing reaches the ledger before review; replaying a source cannot duplicate a transaction |
| AU-01 | P1 | Assisted automatic capture discovery | Design read-only bank-alert email ingestion first; document Android notification/SMS and Account Aggregator trade-offs separately | Provider, consent, revocation, deduplication, latency, cost and privacy are approved before implementation |
| VC-01 | P1 | Voice Capture foundation | Hold-to-record control, permission/offline states, visible editable transcript and handoff into the existing typed capture draft | Audio never writes directly and is not retained by default |
| VC-02 | P1 | Voice understanding | English/Hinglish, Indian amounts, dates, account nicknames, transfers, cards, splits and spoken corrections | Critical accepted cases have exact amount/account/date/type; uncertain and multi-amount speech must clarify |
| VC-03 | P1 | Voice evaluation and QA | Fictional audio/text fixtures, noisy-room and Indian-accent cases, mobile/desktop accessibility and privacy checks | Zero false-ready transfer/card-payment/settlement cases; every ledger write still requires explicit review and confirmation |

## Safe Start fresh contract

The reset preview must show:

- the dated cutoff and timezone (`Asia/Kolkata`);
- how many active transactions will leave live totals;
- which accounts/cards and split participants remain;
- each current balance and proposed new balance;
- the encrypted-backup status;
- the exact effect on spending, income, transfers and shared balances.

The server operation must be owner-only, atomic and idempotent. It should mark
the replaced live period as retired/voided rather than physically deleting
financial rows, write one audit event and then create the new balance snapshot.
A failure at any point leaves the original ledger fully active.

## Voice Capture product contract

Voice is another input surface for the existing safe capture pipeline:

```text
audio -> transcript -> editable source text -> grounded draft -> review -> confirm
```

- The transcript stays visible and editable.
- The model receives the same bounded account/category/member context as typed
  capture; invented IDs are rejected.
- Raw audio is discarded by default after transcription.
- Cloud transcription requires a clear data-use disclosure; on-device
  transcription remains a future option if its accuracy is sufficient.
- Permission denial, silence, interruption, offline state and provider failure
  all preserve a usable manual text path.
- No chain-of-thought is displayed; short progress and clarification messages
  are allowed.

The detailed voice evaluation requirements remain in
[`2026-10-22-real-statement-product-validation.md`](2026-10-22-real-statement-product-validation.md).

## What is deliberately not in this sprint

- Direct bank credential collection or screen scraping.
- Silent automatic ledger writes.
- Investments and portfolio valuation.
- Multi-step agentic financial advice.
- Invited family logins and shared private balances.

## Owner inputs needed at execution time

1. The cutoff date and time after which Artha becomes the source of tracking.
2. The posted balance for every bank/cash/wallet account at that cutoff.
3. The current outstanding, limit, statement day and due day for every card.
4. Which stale accounts should be archived.
5. Approval of the voice transcription/data-use choice after the fictional
   evaluation passes.

