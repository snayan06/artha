# Artha — MVP Product Requirements Document

Status: V1 private pilot; current product contract
Date: 7 August 2026
Product type: Private, shared money-tracking PWA with conversational capture

## 1. Product decision

Build a mobile-first installable web app first. Its main interaction should feel like WhatsApp: type or speak one sentence, review the interpreted transaction, and confirm.

Do not make WhatsApp the only interface. It cannot be guaranteed to remain free, it adds Meta setup and policy dependency, and it makes detailed review and correction harder. Add WhatsApp later as an optional capture channel. A Telegram bot can be the truly free chat-channel experiment if needed.

Working name: **Artha**
Promise: **“Track money in five seconds, understand it anytime.”**

## 2. Problem

Money trackers fail because recording every payment feels like work. They also confuse cash flow with personal spending when expenses are shared. Users need a system that:

- understands natural messages such as “Paid 1840 for groceries from HDFC UPI, split equally with two family members, 3 days ago”;
- remembers accounts, categories, merchants, and common splits;
- shows the real account movement and the user’s actual share separately;
- answers questions in plain language without inventing numbers;
- can later expand to recurring bills, investments, and net worth.

## 3. Users and jobs

### Primary users

- the user: records income, expenses, accounts, and opening balances.
- household members: zero or more configurable family members or other participants. They can be included in splits without requiring a login; invited member access follows later.

### Core jobs

1. Record a payment or receipt in under five seconds.
2. Know how much money exists across accounts.
3. Know what was spent, where, how it was paid, and whether it was shared.
4. Know who owes whom and why.
5. Ask questions such as “How much did I spend on food?”, “What does each family member owe?”, or “Can I spend ₹10,000 this weekend?”

## 4. Product principles

1. **Capture first:** one sentence or one tap should create a complete draft.
2. **Confirm before saving:** AI never silently posts financial data.
3. **Remember preferences safely:** the local/demo rule path learns
   prospectively; production merchant learning must ship as an explicit,
   reviewable integration rather than an implied default.
4. **Cash and expense are different:** a payer’s account may lose the full amount while their personal expense is only their share.
5. **Answers are calculated, not guessed:** the language model interprets the question; database functions calculate the result.
6. **Private by default:** household data is visible only to authorized members.

## 5. MVP scope

### P0 — required for first usable release

- Email magic-link authentication.
- Household creation with zero or more configurable non-login split participants.
- Account setup: cash, bank, UPI-linked bank, credit card, and wallet.
- Opening balance for each account.
- Natural-language debit/credit capture.
- Parsed review: amount, type, merchant, category, account, date, notes, and split.
- Manual edit and confirm.
- Production category suggestion through Gemini, constrained to existing
  household categories, with manual selection on failure. Merchant-rule-first
  behavior is currently local/demo only; production integration is planned.
- Dashboard: available balance, month income, month spend, and pending shared balance.
- Transaction list, search, filters, edit, and soft delete.
- Equal, percentage, or exact shared split.
- Settlement recording.
- Read-only conversational assistant with approved narratives and safe inline
  metrics, charts and transaction tables; all financial values are calculated
  by server/database code.
- CSV export and monthly statement CSV import for reconciliation.
- Installable PWA with an offline draft queue.

### P1 — friction reducers after the core is stable

- Voice capture: “Paid 850 for dinner from ICICI, shared with two family members.”
- Favorite one-tap entries such as rent, maid, and groceries.
- Recurring rules with review reminders.
- Receipt/payment screenshot upload and on-device OCR where practical.
- Android share-target: share a payment screenshot or text to the installed PWA and open a prefilled draft.
- Telegram capture bot.
- Optional WhatsApp Cloud API capture.
- Budget and unusual-spend alerts.

### Later

- V2 member invites so selected family members can sign in, inspect shared items and record settlements.
- Richer assistant filtering, user-selected date ranges, source-linked evidence
  and affordability analysis beyond the current fixed-intent snapshot preview.
- Investments, liabilities, goals, net worth, and asset allocation.
- Bank/email/SMS automation only after legal, privacy, reliability, and cost review.
- Native Android/iOS apps only if PWA capture proves insufficient.

### Explicitly out of MVP

- Direct bank/UPI account aggregation.
- Automatic transaction creation without review.
- Tax advice, investment recommendations, or credit decisions.
- Public social features.

## 6. The five-second capture design

### Primary flow

1. User opens the app directly to a persistent “What happened?” field.
2. User types or speaks one sentence.
3. Gemini interprets the sentence against the authenticated household's known
   accounts, members and categories.
4. A valid result becomes a compact unsaved draft. If interpretation is
   unavailable or invalid, Artha preserves the exact text and opens the manual
   form without guessing.
5. The user reviews and edits the amount, type, accounts, date, category and
   split.
6. User taps **Confirm**. Only then do the ledger, dashboard and shared balance
   update together.

### Example

Input:

> Paid 1840 for groceries from HDFC UPI, split equally with the family, 3 days ago

Draft:

- Type: debit
- Amount: ₹1,840
- Category: groceries
- Paid from: HDFC UPI
- Shared: selected household members, equal or custom amounts
- Account movement: −₹1,840
- the user’s spending: ₹920
- Per-member receivable: calculated from the confirmed split

### Reducing repeated effort

- On the local/demo path, “Reliance Fresh” can learn category `groceries` after
  confirmation; production learning remains planned.
- “from HDFC UPI” becomes the default payment account for UPI entries.
- “split with family” proposes the most recently used member set and ratio.
- Recent merchants and common amounts appear as suggestions, not forced guesses.
- Recurring items create drafts, not final transactions.
- CSV import proposes matches and highlights missing transactions instead of duplicating existing ones.
- When no date is mentioned, the review visibly defaults to today. Relative dates
  such as `yesterday`, `3 days ago`, and explicit unambiguous dates are parsed;
  Today/Yesterday and a date picker remain one-tap corrections.
- When production merchant learning ships, confirmed corrections may update a
  prospective rule and must never rewrite old transactions.

## 7. Core screens

1. **Onboarding:** collect display name, household name, and zero or more family members; add bank/cash/wallet accounts with their current balances; add credit cards with current outstanding, credit limit, statement day and payment due day; review total assets, card liabilities and net opening position. Never collect account numbers, card numbers, PINs, CVVs or OTPs.
2. **Home:** available money, month spend, shared pending, recent activity, top categories.
3. **Quick add:** conversational field, parsed draft, uncertainty indicators, confirm.
4. **Transactions:** searchable ledger with account/category/member/date filters.
5. **Ask:** fixed-intent read-only assistant preview with canonical metrics,
   charts, tables and clarification states.
6. **Family:** per-member net owed/owing, expense details, and settlement actions.
7. **Settings:** accounts, categories, rules, members, export, delete account.

## 8. Key business rules

### Balance calculation

Opening balances are stored as immutable opening entries. Current balance is derived from entries; it is not a manually edited total.

### Shared expense

For a ₹1,840 transaction paid fully by the user and shared with one member equally:

- HDFC cash movement: −₹1,840
- the user personal expense: ₹920
- member personal expense: ₹920
- member payable / the user receivable: ₹920

A later settlement changes cash and clears the receivable; it does not count as new income or spending.

### Credit card

A card purchase increases card liability. Paying the card is an account transfer from bank to card and must not be counted as spending twice.

### Corrections

Edits preserve an audit record. Deletes are soft deletes. Recalculations happen transactionally so balances, splits, and settlements cannot diverge.

## 9. Ask Artha current preview

The current preview supports exactly eight intents:

| Intent | Canonical result |
|---|---|
| `summary` | Total balance, current-month spending and current-month income metrics, in that order |
| `spending` | Current-month spending metric plus a top-category bar chart when category data exists |
| `income` | Current-month income metric |
| `cashflow` | Monthly income then monthly spending line charts, or clarification when monthly context is empty |
| `shared` | Household-balance table, or clarification when member context is empty |
| `transactions` | Recent-activity table, or clarification when transaction context is empty |
| `clarification` | Approved question and choices for an unclear request |
| `unsupported` | Read-only boundary message and approved alternatives |

Pipeline:

1. FastAPI builds a bounded snapshot from authenticated dashboard context:
   total balance, current-month spend/income, up to 20 member balances, 5 top
   categories, 6 monthly points and 8 recent transaction summaries.
2. Server code builds the exact approved narrative and canonical widget array
   for each intent.
3. Gemini selects an intent and must copy that intent's narrative and bundle.
4. FastAPI requires exact equality for titles, labels, values, rows, points,
   order and cardinality.
5. React renders repository-owned components.

The model never calculates authoritative financial values, changes the ledger,
emits arbitrary numeric prose or supplies executable HTML. If it is unavailable
or returns an invalid contract, the API returns a sanitized `503` and the
interface shows an honest error rather than a generated fallback.

This preview answers from the current bounded snapshot; it does not yet offer
arbitrary filters, custom date ranges, affordability analysis or source-linked
drill-down. Those remain explicit future capabilities.

## 10. Data model

- `profiles`: user identity and preferences.
- `households`: private shared space.
- `household_members`: member, role, status.
- `accounts`: name, type, currency, owner, active state.
- `transactions`: household, account, type, amount, date, merchant, note, source, status.
- `categories`: household categories and parent category.
- `transaction_splits`: responsible member, amount or percentage.
- `settlements`: from member, to member, amount, linked transaction.
- `transfer_links`: connects the two sides of account transfers.
- `merchant_rules`: remembered merchant/category/account defaults.
- `recurring_rules`: schedule and draft template.
- `attachments`: receipt reference and OCR status.
- `audit_events`: who changed what and when.

All money values use integer paise, never floating-point numbers.

## 11. Free-first architecture

| Layer | Choice | Why |
|---|---|---|
| Product design | Figma Starter | Free personal drafts, components, Auto Layout, clickable prototype |
| Client | React + TypeScript + Vite PWA | Fast, installable, familiar ecosystem |
| UI | Tailwind CSS + repository UI components | Accessible controls and quick iteration without an unused framework dependency |
| Hosting | Vercel Hobby | Two personal projects for the Vite PWA and FastAPI monorepo roots |
| Auth + database | Supabase Free | Managed Postgres, magic links, row-level security, realtime, storage |
| API | Python 3.13 + FastAPI + Pydantic v2 on Vercel | Typed APIs without a minute-long container wake-up |
| Assistant | Gemini via the official Google SDK, strict Pydantic schemas and server-owned canonical bundles | Fixed-intent read-only preview; exact titles, values, rows, order and cardinality come from bounded database context |
| Natural-language capture | Gemini via the official Google SDK, grounded in authenticated household context | Strict validated unsaved drafts; preserved text and manual form when interpretation is unavailable |
| Auto-tagging | Production Gemini suggestion; merchant-rule-first matching remains local/demo pending Supabase integration | Only existing household categories may be selected; manual selection on failure |
| Voice | Cloudflare Workers AI Whisper, capped | Free allocation is sufficient for a private pilot |
| OCR | Client-side OCR first | Keeps screenshots private and avoids API cost |
| Source + CI | GitHub Free + GitHub Actions | Version control and automated checks |
| Monitoring | Sentry free tier or structured server logs | Enough for an MVP |
| Domain | `*.vercel.app` initially | ₹0; a custom domain is optional and normally paid |

Current free-tier evidence:

- [Supabase Free](https://supabase.com/pricing) currently includes 500 MB database, 1 GB storage, 50,000 MAU, and two active free projects; inactive free projects may pause after a week.
- [Vercel Hobby](https://vercel.com/docs/plans/hobby) supports personal non-commercial projects within included usage limits.
- [Vercel FastAPI](https://vercel.com/docs/frameworks/backend/fastapi) supports a Python FastAPI application as one function; the Python runtime remains beta.
- [Render Free](https://render.com/docs/free) remains a fallback, but spins Python web services down after 15 idle minutes and may take about a minute to restart.
- [Cloudflare Workers Free](https://developers.cloudflare.com/workers/platform/pricing/) currently includes 100,000 requests/day, while static asset requests are free.
- [Cloudflare Workers AI](https://developers.cloudflare.com/workers-ai/platform/pricing/) currently has a 10,000-neuron/day free allocation.
- [Cloudflare Pages Free](https://developers.cloudflare.com/pages/platform/limits/) currently includes 500 builds/month.
- [Figma Starter](https://www.figma.com/pricing/) is free; personal drafts are the best place to avoid the free team-file/page limit.

Free tiers and policies can change. The app must fail closed at quotas and must never silently enable billing.

### WhatsApp warning

WhatsApp Business Platform pricing and policies are changing and cannot be treated as permanently free. Keep the PWA as the source-of-truth interface. If WhatsApp is added, use it only as an input adapter and confirm the live Meta pricing at implementation time.

## 12. Security and privacy

- Supabase Row Level Security on every household table.
- Household membership checked server-side for every write and query.
- Service-role and AI keys only in server-side secrets.
- Magic links in MVP; passkeys can follow.
- Raw account numbers and card numbers are never needed or stored.
- Mask household/member/account names before sending text to an external model where possible.
- LLM output validated against a strict schema.
- Rate limit capture and Ask endpoints.
- Export and permanent-delete flows.
- Automated database backup export to the owner’s device until managed backups are affordable.

## 13. Figma prototype plan

Use one Figma Draft file named `Artha — MVP`. Starter is suitable for a personal prototype, but View-seat MCP automation is heavily rate-limited; design work may need to continue manually or after quota renewal.

### Page 1 — Foundation

- Color, typography, spacing, icons.
- Components: transaction row, amount, account chip, category chip, member chip, parsed field, confidence warning, buttons, bottom navigation.

### Page 2 — Mobile flows

Create 390 × 844 frames for:

1. Welcome / magic link
2. Account and opening-balance setup
3. Home
4. Quick-add empty state
5. Parsed shared-expense review
6. Ask result
7. Shared settlement
8. Transaction correction

### Page 3 — Clickable prototype

Prototype these tasks:

- Add “₹1,840 groceries from HDFC, shared with two family members.”
- Correct an incorrectly detected category.
- Ask how much was spent on food this month.
- Check why one family member owes ₹2,140 and mark it settled.

### User-test success criteria

- A first-time user completes each task without explanation.
- Median transaction capture is under 10 seconds initially; after production
  merchant-rule integration, the target is under 5 seconds for a learned merchant.
- No participant confuses account cash movement with personal share.
- Users can always tell whether a transaction has been saved or is still a draft.

### Ready-to-paste Figma Make prompt

> Design a mobile-first personal and shared money tracker named Artha for a configurable household with zero or more family members. Use a calm, trustworthy green-neutral visual system, INR formatting, 390x844 mobile frames, accessible contrast, and bottom navigation: Home, Add, Insights, Family. The primary action is a conversational field labeled “What happened?” that turns “Paid 1840 for groceries from HDFC UPI, split equally with two family members, 3 days ago” into a review card showing debit, amount, groceries, HDFC UPI, date, selected members, account movement, personal expense, and per-member receivables. Never auto-save; include a clear Confirm button and uncertainty states. Create Home with a six-month spending chart, onboarding/opening balances, quick-add text and form modes, parsed review, transactions, family settlement, and correction screens. Also show a read-only assistant chat that can render approved inline charts, cards and transaction tables. Keep the interface compact, friendly, and data-first; avoid crypto visuals and dense finance dashboards.

## 14. Framer’s role

Framer is optional and should not be used to build the actual money application. Use its free plan only to test a simple public landing page with:

- “Track money in five seconds.”
- a short capture animation;
- shared-expense explanation;
- privacy promise;
- waitlist or sign-in link.

The application itself needs database transactions, authentication, offline behavior, and row-level security, which belong in the React/Supabase build.

## 15. Four-week MVP plan

### Week 0 — validate the interaction (2–3 days)

- Figma foundation and eight mobile frames.
- Clickable capture/shared/Ask prototype.
- Test with the owner first, then validate shared-language clarity with multiple household members.

### Week 1 — trustworthy ledger

- Repo, CI, PWA shell, authentication and the FastAPI service.
- Accounts, opening balances, transaction model, row-level security.
- Dashboard and manual transaction entry.

### Week 2 — five-second capture (original roadmap)

- Gemini interpretation, strict draft validation and manual recovery.
- Review/confirm/edit flow.
- Merchant memory, categories, recurring favorites.
- Offline drafts and installation.

### Week 3 — shared money and Ask

- Splits, receivables, settlements.
- Fixed-intent Ask preview with bounded context and canonical server-owned bundles.
- CSV export/import and reconciliation.

### Week 4 — hardening and private launch

- Mobile QA, accessibility, error states, audit trail, rate limits.
- Security review and backup/export test.
- Deploy the PWA and FastAPI as separate Vercel projects; connect the fresh Supabase project and onboard the user.
- Observe capture time and missing-transaction rate for two weeks.

## 16. MVP acceptance gate

The MVP is ready only when:

- the owner can sign in and see only their household; multiple participants are represented correctly in shared splits without a V1 login.
- Opening balances reconcile with dashboard totals.
- Natural debit, credit, transfer, and shared entries parse into drafts.
- No transaction is saved without confirmation.
- Full account movement and personal share are both correct.
- Editing/deleting a shared expense recalculates all balances atomically.
- Settlement does not inflate income or expense.
- Assistant narratives and canonical bundles match the selected intent and
  bounded server context exactly.
- CSV export can reconstruct the ledger.
- Installed PWA works on Android and iPhone; offline entries remain drafts until synced.
- The service operates at ₹0 within documented quotas, excluding an optional custom domain and WhatsApp.

## 17. Product metrics

- Median capture time.
- Percentage of drafts confirmed without edits.
- Parser correction rate by field.
- Transactions recorded per active week.
- Imported statement transactions missing from Artha.
- Shared-balance disputes/corrections.
- Assistant requests resolved to a supported, clarification or unsupported intent.
- Assistant model-unavailable and invalid-contract rate.

The key launch metric is not sign-ups; it is **at least 90% of real transactions captured for four consecutive weeks without the process feeling burdensome**.
