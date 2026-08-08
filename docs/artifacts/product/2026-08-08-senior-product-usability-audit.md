# Artha senior product audit — private pilot

Date: 8 August 2026
Recommendation: approve deployment for fictional private-pilot testing after
the engineering release gates pass. Do not approve real financial data yet.

## Target user and core job

Artha's primary user manages money across several bank accounts and credit
cards, with some expenses shared among friends or family.

> Record what happened in seconds, confidently verify what Artha understood,
> and keep personal balances, account movements and shared obligations accurate
> over time.

The product succeeds when capture becomes a dependable daily habit, not when it
adds the most finance or AI features.

## End-to-end journey review

| Stage | Current strength | Important gap |
| --- | --- | --- |
| Sign-in | Clear magic-link copy and recovery states | Full browser-reopen and second-device continuity still need acceptance |
| Onboarding | Multiple accounts, cards, balances and participants | Long setup is not resumable; accounts cannot be maintained afterward |
| Daily capture | Natural language, Indian shorthand, backdates and transfers create reviewable drafts | Manual recovery supports only expenses; transaction type cannot be corrected |
| Review | Amount, account, date, category and equal splits are visible | Category accepts unrestricted text although production requires a known category |
| Confirmation | Explicit confirmation, idempotency and duplicate protection | No immediate transaction detail, undo or correction path |
| Dashboard | Total, monthly cash flow, shared balance and recent activity | Users with several accounts cannot see a current balance per account |
| Transactions | Search plus type and account filters | No transaction detail, correction or soft-delete UI |
| Shared money | Correctly separates account movement from personal share | No member-paid expense or settlement workflow, so the loop cannot close |
| Assistant | Read-only, fixed-intent and server-grounded | Evidence range, source count and transaction drill-down are absent |
| Settings | Strong client-side encrypted export | No account/family management, provider disclosure or data deletion |
| Reliability and privacy | Honest unavailable states and sanitized telemetry URLs | Production isolation/restore remain incomplete; Gemini data-use warning is documentation-only |

## Prioritized gaps

### P0 — required before real financial use

#### Production isolation and recovery acceptance

Status: already planned and already a release blocker.

Why it matters: financial correctness is insufficient if one owner can access
another household or recovery has not been proven on the final environment.

Acceptance:

- two independent owners cannot read, mutate or infer each other's household;
- encrypted export restores into a fresh production household;
- accounts, transactions, transfers, splits, balances and audit facts reconcile;
- browser/API logs contain no tokens, financial payloads or model prompts;
- sanitized fictional-data evidence is recorded.

Placement: finish the current release gate before real-data use.

#### Complete manual capture recovery

Status: net-new; changes the current display-only transaction-type contract.

Why it matters: when Gemini is unavailable or misclassifies a transaction,
manual entry defaults to an expense. The user cannot manually enter income or a
transfer or correct the detected type.

Acceptance:

- manual entry offers Expense, Income and Transfer;
- switching type changes required account fields safely;
- transfers require different source and destination accounts;
- exact original text remains available after AI failure;
- nothing is saved until confirmation;
- automated and manual tests cover all three types and unavailable recovery.

Placement: current release hardening.

#### Constrain category correction

Status: net-new UX hardening; category management itself is already planned.

Why it matters: review accepts arbitrary category text, but production
confirmation accepts only existing household categories. A reasonable-looking
correction can therefore fail only after confirmation.

Acceptance:

- review uses a server-owned category select/search control;
- only categories valid for the transaction type are offered;
- loading and unavailable states are explicit;
- invalid categories are prevented before submission;
- selection remains editable without rerunning Gemini.

Placement: current release hardening.

#### Provide immediate post-confirmation recovery

Status: edit and soft delete are already planned; the success-screen recovery
entry point is net-new.

Why it matters: even with review-before-save, users will occasionally confirm
the wrong amount, account, date or split. Without correction, one mistake
damages trust in every total.

Acceptance:

- success includes **View transaction**;
- transaction detail supports audited edit and soft delete, or a safe
  short-lived undo;
- corrections recalculate dashboard, account and shared balances atomically;
- removed records remain auditable;
- retries are idempotent.

Placement: first Sprint 2 slice, before broader management work.

#### Make AI data use visible in-product

Status: net-new provider disclosure; AI-learning consent controls are already
planned separately.

Why it matters: the repository warns that free-tier Gemini should receive only
fictional data, but capture and assistant screens do not communicate that
boundary. Documentation is not meaningful user consent.

Acceptance:

- first use explains that capture/assistant text is sent to the configured AI;
- the fictional-data/private-pilot restriction is explicit;
- Settings shows provider, purpose and applicable privacy mode;
- real-data use remains blocked until an approved privacy configuration exists;
- consent telemetry contains no financial text or identifying labels.

Placement: current fictional-pilot hardening; approved provider configuration
before real-data use.

#### Add account-context loading recovery

Status: net-new.

Why it matters: Quick Add has no visible retry path if account loading fails,
so confirmation can remain disabled without explaining what is missing.

Acceptance:

- account-loading failure produces an accessible error and retry action;
- confirmation explains why it is disabled;
- retry does not erase typed text or the unsaved draft;
- no unhandled browser error occurs.

Placement: current release hardening.

#### Align release documentation with production behavior

Status: net-new release hygiene.

Why it matters: some QA artifacts still describe deterministic production
fallback although the approved path is Gemini-only with manual recovery.

Acceptance:

- active QA artifacts describe Gemini → validated draft → review;
- capture failure preserves text and opens manual recovery without guessing;
- assistant failure is an honest unavailable state, not generated fallback UI;
- historical benchmarks are visibly historical.

Placement: before publishing the current candidate.

### P1 — highest-value next sprint

#### Accounts and family management with per-account balances

Status: already planned in Sprint 2A.

Acceptance: show current balance/outstanding per account; add, rename, archive
and restore accounts/cards and participants; record audited adjustments; retain
historical labels; pass owner-only authorization before invitations.

#### Close the shared-money loop

Status: settlement UI is planned; member-paid capture is net-new web scope.

Acceptance: record a member-paid expense without moving the owner's account;
record incoming/outgoing settlements; update shared balances without changing
income/spending; explain which expenses and settlements form each balance.

#### Improve first-session activation

Status: net-new.

Acceptance: preserve unfinished onboarding locally; show field-level validation;
guide the user to a first transaction; give empty Home and Transactions states a
clear next action; never persist identifiers Artha does not otherwise collect.

#### Add privacy-safe product instrumentation

Status: product metrics exist, but implementation is mostly net-new. Sanitized
Vercel page/performance telemetry is already shipped.

Acceptance: measure onboarding completion, draft creation, confirmation time,
edited field names, enumerated failure class and weekly confirmed count; never
send text, amounts, balances, emails, account/member/household names or assistant
questions; document retention and an analytics disable path before expansion.

#### Assistant evidence and drill-down

Status: already planned.

Acceptance: show evidence date range and matching count; link supported results
to a filtered ledger; keep values server-calculated; preserve explicit empty and
unsupported states.

#### Invite family only after owner-only hardening

Status: already planned in Sprint 2B.

Acceptance: a viewer sees only activity involving their linked participant;
private accounts, ledger, assistant, exports and other people remain hidden;
invite lifecycle and two-owner/two-viewer isolation pass in production.

### P2 — later improvements

Already planned: custom splits, reviewed merchant learning, favourites,
recurring drafts, CSV reconciliation, offline draft queue, OCR, voice, share
target, and private-data deletion/export.

Net-new retention idea: a missing-transaction reminder and an optional weekly
review after daily capture is proven reliable.

## Success metrics

The main launch metric should remain:

> At least 90% of the user's real transactions captured for four consecutive
> weeks without the process feeling burdensome.

| Area | Metric |
| --- | --- |
| Activation | Sign-in → onboarding completion; onboarding → first confirmed transaction |
| Capture speed | Median time from opening capture to confirmation |
| Understanding | Confirmed without edits; correction rate by amount/account/date/category/type/split |
| Reliability | Account-load, AI-unavailable, invalid-contract and confirmation-failure rates |
| Trust | Post-confirm correction/delete rate; duplicate writes; unresolved balance discrepancies |
| Habit | Confirmed transactions per active week; four-week capture coverage |
| Shared | Shared expenses settled; shared-balance correction/dispute rate |
| Assistant | Supported, clarification, unsupported and unavailable rates; evidence drill-through |
| Recovery | Successful export rate and restore-drill completion |

Instrumentation must never contain transaction text, descriptions, amounts,
balances, account/card names, emails, people/household names, assistant questions
or responses, authentication material or backup data. Use event names, coarse
duration buckets, enumerated field names and success/failure classes. Do not use
Session Replay on financial screens.

## Do not build yet

Defer these until capture, correction, settlement, isolation and retention are
proven:

- WhatsApp or Telegram capture;
- voice entry and receipt OCR;
- bank, SMS or email aggregation;
- budgets and unusual-spend alerts;
- investments, liabilities and net worth;
- affordability or financial-advice assistant features;
- public sharing or social features;
- automatic transaction confirmation;
- generative UI beyond repository-owned safe widgets.

The immediate opportunity is not more AI breadth. It is making ordinary daily
capture recoverable, correctable and trustworthy across multiple accounts and
shared-family situations.
