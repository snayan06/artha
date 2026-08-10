# Senior product review — daily-use V1

Date: 10 August 2026

## Product verdict before this release

Artha had a strong capture and ledger foundation, but it was not yet a complete
daily-use loop. A user could add money movements and inspect summaries, yet
ordinary maintenance actions still ended in dead ends.

## V1 gaps and decisions

| Finding | Why it matters in daily use | Decision |
| --- | --- | --- |
| Search covered only loaded recent activity | A forgotten older purchase looked missing | Search the full owner ledger in the database and add stable **Load older activity** browsing; search returns the first 200 relevant matches |
| No transaction detail/correction | One typo permanently damaged trust in totals | Open every row; correct through one atomic audited void-and-replacement operation |
| No safe duplicate removal | Duplicate capture could not be recovered | Require a reason and remove the logical activity from totals while preserving audit history |
| Confirmation had no recovery action | Users could not verify what was just saved | Offer **View transaction** immediately after confirmation |
| Shared balance had no repayment action | “Owes you” never reached settled | Record a repayment through one atomic replay-safe command against the exact database balance without classifying it as spending/income |
| Accounts/cards stopped at onboarding | Real account changes forced a reset | Add/edit/archive/restore and audited reconciliation; already deployed before this slice |
| AI disclosure dominated Settings | Users saw policy prose instead of a clear status | Lead with one plain-language status and collapse provider details |
| Mobile dialogs lacked a common interaction contract | Keyboard and small-screen recovery was inconsistent | Shared focus entry, focus trap, Escape close, scroll lock and focus restoration |

## Product principles retained

- AI proposes; the user reviews; server-owned code validates and writes.
- Corrections and removal preserve audit history.
- Transfers do not count as income or spending.
- Repayments reduce a shared balance without distorting spending or income.
- Search and shared balances are database-derived rather than inferred from a
  row-limited browser cache.
- No chain-of-thought is exposed. Progress messages explain the operation being
  performed, while answers remain grounded in server-owned facts.

## Deliberately deferred to the next sprint

1. Paid/private-data AI approval plus an explicit owner control.
2. Member-paid shared expenses.
3. Participant add/rename/deactivate controls.
4. Email invitations and a restricted **Shared with me** experience.
5. Evidence-backed assistant answers with date range, source count and matching
   transactions.
6. Investment product discovery for mutual funds and stocks.

These are ordered on the [sprint board](../../SPRINT-BOARD.md). Invitations and
investments should not be rushed into the daily-use release because each needs
its own permission and accounting model.
