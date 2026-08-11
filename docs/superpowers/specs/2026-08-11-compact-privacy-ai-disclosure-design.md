# Compact Privacy & AI Disclosure Design

**Status:** approved for implementation

## Goal

Keep Artha's third-party AI and analytics disclosure available without making
AI a primary Settings theme or implying that the disclosure is an interactive
privacy control.

## Information hierarchy

The Settings page keeps money-management tasks first:

1. Accounts and cards.
2. Encrypted backup and restore.
3. Backup safety guidance.
4. A quiet, collapsed **Privacy & AI** disclosure at the bottom.

The existing large **AI and data use** card, green enabled-state banner and
**Privacy controls** label are removed. The replacement is one compact
`details` row. Its summary reads **Privacy & AI** with the supporting line
**How Artha uses AI and analytics**. It is collapsed by default.

## Expanded disclosure

When opened, the row explains only the facts needed for informed use:

- whether private financial text is enabled for the current account;
- capture and Ask Artha use limited, task-relevant context;
- AI can prepare drafts and read-only answers but cannot write to the ledger;
- every transaction still requires explicit confirmation;
- the current server-configured provider and model;
- requests use `store=false`, without presenting that as a broader retention
  guarantee; and
- Vercel analytics receives no financial text, amounts, emails, account/member
  names or assistant questions.

If personal-data AI is unavailable, the expanded copy says so and points to
manual entry. The summary remains neutral rather than advertising AI status.

## Accessibility and responsive behavior

- Use native `details` and `summary` semantics.
- Keep a minimum 44 px summary target and a visible focus ring.
- Keep the disclosure readable in light and dark themes at 320 px and above.
- Do not add a modal, toggle or navigation state for a read-only disclosure.

## Test contract

- The disclosure appears after the account and recovery content.
- Provider and data details are hidden until the row is expanded.
- Approved and sample-only server policies render accurate expanded copy.
- The old **AI is enabled for this account** banner and **Privacy controls**
  label are absent.
- Existing account management and recovery behavior remains unchanged.

