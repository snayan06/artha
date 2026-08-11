# Private WhatsApp history import plan

Date: 11 August 2026

Status: post-August 13 product and architecture plan; not implemented
Data boundary: local analysis only; no raw personal messages are committed or
sent to an LLM, analytics provider or external service

## Decision

Treat an existing WhatsApp money-log export as a **historical import source**,
not as a live messaging integration. The browser reads the archive locally and
turns possible entries into an editable staging table. Artha receives only the
structured rows the signed-in owner reviewed and selected. Nothing reaches the
ledger until the owner explicitly confirms the complete import summary.

This is separate from a future WhatsApp bot. It needs no WhatsApp business
account, webhook or provider API.

## Redacted local evidence

The authorized local export was inspected without uploading it or printing raw
messages. The archive itself remains outside the repository.

| Observation | Aggregate result |
| --- | --- |
| Export shape | One UTF-8 text export |
| Parsed chat records | 71 timestamped messages and one continuation line |
| Time coverage | Roughly eight weeks across three calendar months |
| Participants | Three senders; anonymized message counts 67, 3 and 1 |
| Numeric candidates | 64 messages contain at least one numeric token |
| Likely amount-first rows | 57 messages begin with a numeric token |
| Single/multiple/no numeric candidate | 56 / 8 / 7 |
| Anonymized numeric-candidate distribution | 61, 3 and 0 by sender |
| Exact normalized duplicates | None observed |
| Attachments or deleted-message markers | None observed |

These are candidate counts, not confirmed transaction counts. A number can be
a split, date, reference or note. The importer must never interpret all 64 rows
as ledger writes automatically.

## Owner journey

1. **Choose the export.** The browser opens the ZIP locally; the archive is not
   uploaded.
2. **Set import context.** Confirm the source timezone, map each sender to the
   owner, a household participant or Ignore, and choose a default account.
3. **Review candidates.** Each row shows the proposed date, amount, description,
   type, account, category, payer and split. Ambiguous fields are visibly
   incomplete, not silently defaulted.
4. **Resolve warnings.** Multiple-number rows require amount selection; rows
   without an amount remain skipped or are completed manually. Transfers require
   both accounts.
5. **Check duplicates.** Exact replays are preselected for Skip. Similar rows
   show a warning and remain an owner decision.
6. **Confirm once, explicitly.** The final summary separates rows to create,
   skip and block. The write button states the exact number of reviewed entries.
7. **Verify the result.** Artha opens a filtered transaction view for the import
   batch and shows any rows that were skipped as existing records.

Closing or reloading the first implementation can discard the staging table.
Resumable encrypted local staging is a later enhancement, not a reason to store
raw chat content on the server.

## Local parser contract

The parser is deterministic and runs in the browser or a local worker. It does
not call Gemini, ADK or another hosted model.

- Recognize common bracketed and dash-separated WhatsApp timestamps.
- Require an explicit timezone because the export contains local wall-clock
  time without a timezone. Default the proposal to `Asia/Kolkata`, then convert
  reviewed values to UTC for persistence.
- Use the chat timestamp as the proposed transaction time. An explicit date in
  the message is a review suggestion, never an unchecked override.
- Parse rupees into integer paise without floating-point arithmetic. Support
  plain integers, Indian comma grouping, up to two decimal places and reviewed
  `k`, `thousand`, `lakh` or `lac` suffixes.
- Reject zero, negative, out-of-range or more-than-two-decimal amounts.
- Preserve the candidate description for review but do not persist the full raw
  message as notes or learning history.
- Treat expense, income and transfer as explicit reviewed fields. A default may
  prefill the form but remains visually marked as a default.
- Do not infer an account, category, payer or split from weak text. Offer the
  owner's active server-provided choices.

The personal export is not an eval fixture. Parser tests use fabricated messages
covering format, amount, date, multiline, ambiguity and malicious-input cases.

## Structured row sent after review

Each selected row maps to the existing ledger concepts:

| Field | Rule |
| --- | --- |
| `kind` | `expense`, `income` or `transfer` |
| `amount_paise` | Positive integer paise |
| `description` | Required, reviewed, maximum 240 characters |
| `occurred_at` | Required timezone-aware historical timestamp |
| `source_account_id` | Active account in the owner's household |
| `category` | Required and direction-valid for expense/income |
| `destination_account_id` | Required only for transfers and different from source |
| `paid_by_member_id` | Owner or mapped participant when supported |
| `personal_share_paise` and `splits` | Must add exactly to the total |
| `source_fingerprint` | Household-scoped keyed digest; never raw message text |

The browser may send the reviewed description because it becomes the ledger
description. It must not send the archive, sender labels, unselected messages or
original raw lines.

## Duplicate and retry safety

- Create a stable, household-scoped HMAC fingerprint from the canonical local
  timestamp, sender mapping and normalized source line. A server-provided
  household import salt prevents useful offline guessing from stored digests.
- Record accepted fingerprints in a private, RLS-protected import table with a
  unique household/source constraint.
- Re-importing the same export returns the existing result instead of creating
  another transaction.
- Flag near duplicates using reviewed date, paise, type, account and normalized
  description; never delete or skip a near match without the owner's choice.
- Use one batch idempotency key and one bounded, atomic database RPC. Either all
  new reviewed rows and their fingerprints commit, or none do.
- Limit the first version to 100 candidates per batch and show deterministic
  per-row validation errors before confirmation.

## Important ledger gap

The current owner flow cannot safely represent every transaction entered by a
different sender. A participant-paid expense must create the owner's payable or
receivable without moving the owner's bank account. Until the planned
member-paid-expense slice exists, mapped non-owner rows remain blocked or
ignored; they must not be imported as if the owner paid them.

## Proposed implementation slices

| ID | Slice | Acceptance gate |
| --- | --- | --- |
| WI-01 | Browser-local ZIP and text parser with synthetic fixtures | Raw archive never leaves the device; malformed/multiline exports fail safely |
| WI-02 | Sender, timezone and default-account setup | All three mappings are explicit and active household IDs are server-grounded |
| WI-03 | Responsive staging table and row editor | Every required field is visible; blocked, skipped and ready states work at 320, 390 and 1440 px |
| WI-04 | Duplicate preview and private fingerprint registry | Exact replay creates zero duplicates; near matches require a choice |
| WI-05 | Atomic reviewed-batch RPC and audit event | Retry is idempotent; a forced failure leaves zero partial ledger rows |
| WI-06 | Post-import verification and recovery coverage | Batch filter matches created rows; encrypted export/restore preserves imported ledger facts |

## Release gates

- No raw personal export, message, sender label or real amount appears in Git,
  logs, screenshots, analytics, Sentry or model prompts.
- No candidate is saved before a visible review and explicit batch confirmation.
- Every amount uses integer paise and every split balances exactly.
- Same archive and overlapping-export replay tests create no duplicate facts.
- Non-owner payer semantics pass before participant rows can be selected.
- Household isolation, RLS, atomic rollback, encrypted recovery and mobile/dark
  UI checks pass with fictional fixtures.
- `make check`, migration contracts, CI, CodeQL and signed-in fictional final-
  domain acceptance pass before deployment.

## Deliberate non-goals

- No hosted AI interpretation of this personal archive.
- No direct ledger writes from a parser, ADK agent or messaging webhook.
- No automatic bulk category choice from uncertain text.
- No live WhatsApp ingestion, background synchronization or provider account in
  this slice.
- No commit of sanitized excerpts derived from the personal archive; eval data
  remains independently fictional.
