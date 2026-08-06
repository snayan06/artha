# Sprint 2 product contract — Accounts & family

Date: 6 August 2026  
Status: implementation-ready scope; no application code changed  
Owner outcome: maintain banks, cards and family after onboarding, then invite a
person without exposing the private ledger

## Product boundary

Sprint 2 is delivered in two releasable slices:

1. **Sprint 2A — owner maintenance:** Accounts & family settings, account/card
   maintenance, audited balance corrections and non-login participant
   maintenance.
2. **Sprint 2B — limited collaboration:** invitation lifecycle, least-privilege
   shared read models and an invited person's shared-only experience.

Sprint 2A may ship after the Sprint 1 production acceptance gate. Sprint 2B must
remain feature-flagged until its RLS and two-identity security suite passes in
production. A non-login participant remains fully usable for splitting even if
invitations are never enabled.

## Current-state findings

| Finding | Product consequence |
| --- | --- |
| Production exposes only `GET /api/v1/accounts`, `GET /api/v1/members` and onboarding setup for this area. | Add, rename, archive, correction and invitation commands need production contracts; the local demo routes are not production capability. |
| The local demo API can add accounts/members and directly patch `opening_balance_paise`. | Do not promote the direct opening-balance mutation. It rewrites the baseline and conflicts with the audited-ledger principle. |
| Production `accounts` already has account type, currency, opening balance, card limit, statement day, due day and `is_archived`; active names are case-insensitively unique. | Reuse these constraints and add owner-only commands rather than introducing another account model. |
| `household_members` already distinguishes an authenticated `user` from a non-login `participant`; transaction splits and settlements reference the member row ID. | Invitation acceptance should link the existing participant row so historical splits keep the same identity. |
| Roles currently allow only `owner` and `member`; there is no invitation table, lifecycle or token model. | Add a versioned `shared_viewer` role and a separate invitation lifecycle before any invitation UI. |
| Current `is_household_member` RLS grants every active user membership access to accounts, all transactions, splits, settlements, merchant rules and audit events; it also permits member account writes. | A shared viewer must never be inserted under the current broad policies. Base-table policies must become owner-only, with separate minimal shared RPC projections. |
| `get_current_household()` rejects more than one active household membership. | An invitee who owns a private ledger cannot be added to the existing context model. Owner-ledger context and “shared with me” access must be resolved separately. |
| The logical activity projection is owner-specific and returns private notes, account IDs and other members' split data. | Do not reuse it for viewers. Build an explicit shared-only projection with a smaller field set. |
| There is no balance-adjustment direction in the production transaction constraint or logical activity projection. | Balance correction requires a first-class audited ledger movement and corresponding balance/export/history handling. |
| Account and participant creation currently cap onboarding at 20 items each. | Preserve the 20 active-account and 20 active-participant pilot limits unless later usage proves a need to raise them. |

## Decisions and invariants

- Money remains integer paise. No floating-point amount enters an API or table.
- Account type and currency are immutable after creation. A wrong type is
  corrected by creating the right account and transferring/adjusting explicitly.
- An opening balance is an immutable tracking baseline. It is never edited after
  account creation.
- A later balance correction is a new ledger fact, not income, spending,
  transfer, settlement or a historical rewrite.
- Accounts and people are archived/deactivated, never hard-deleted, once they
  have ledger references.
- Account, participant and invitation writes are owner-only and idempotent.
- Invitation acceptance preserves the participant row ID and its historical
  splits.
- The first authenticated invited role is read-only `shared_viewer`.
- A viewer sees only facts involving their linked member identity. UI hiding is
  not authorization; Postgres RLS/RPC checks are the enforcement boundary.
- No account/card number, CVV, PIN, OTP, password or email token is collected or
  stored by Artha.
- Every correction, rename, archive, restore, invitation, acceptance and
  revocation emits an audit event with the actor and safe before/after metadata.

## Ordered implementation scope

### S2-01 — owner settings foundation

**User story:** As the owner, I can open **Accounts & family** after onboarding
and understand all active and archived items without re-running setup.

Scope:

- Add one owner-only settings read model containing active/archived accounts,
  card metadata, current balances, participants and access status.
- Keep archived items in a separate collapsed section.
- Add server-side owner authorization; never rely on a browser role flag.
- Use loading, empty, stale-session, offline and retry states consistent with
  Sprint 1.

Acceptance:

- A returning owner sees server data on another device with no onboarding
  repeat.
- A non-owner receives `403` for the settings read model even if they know IDs.
- No settings response includes invitation tokens, raw auth metadata or audit
  payloads.

### S2-02 — add and maintain banks, cash, wallets and cards

**User story:** As the owner, I can add an account, correct its display metadata
and retire it without losing history.

Scope:

- Add bank, cash, wallet, credit-card and other account types up to the pilot
  limit.
- Require trimmed, case-insensitively unique active names.
- Allow rename for every type.
- Allow card limit, statement day and due day updates; card outstanding is a
  balance, not editable card metadata.
- Show an over-limit warning when current outstanding exceeds a newly entered
  limit, but allow the truthful state to be saved.
- Archive only after explicit confirmation. Offer restore when no active account
  has the same normalized name.
- Remove archived accounts from Quick Add defaults and transfer selectors while
  retaining them in history and account filters.

Acceptance:

- Non-card accounts reject card-only metadata; card days accept only 1–31 or
  blank; limits accept non-negative integer paise.
- Type and currency cannot be patched.
- Renaming changes the current display label across history; the audit event
  retains the previous label.
- An account with a non-zero balance cannot be archived. The UI directs the
  owner to transfer or correct it to zero first.
- The last active account cannot be archived.
- Active merchant defaults that reference an account must be reassigned or
  disabled before archive; no hidden rule continues selecting it.
- Historical transactions, linked transfers and settlements remain readable
  after archive/restore.
- Duplicate retries produce one account or one state transition.

### S2-03 — audited balance correction

**User story:** As the owner, when Artha and the real account disagree, I can set
the observed balance and see the exact correction before confirming.

Scope:

- The UI asks for **actual balance now**, a required reason and an effective
  date, then previews the signed delta from Artha's authoritative balance.
- For a credit card, the UI asks for positive **outstanding due** and clearly
  maps it to a liability balance.
- Confirmation creates one `adjustment_in` or `adjustment_out` ledger movement
  through an atomic, idempotent RPC.
- The server recomputes current balance at confirmation. If it changed after the
  preview, return a conflict and require a refreshed review.
- A posted correction is reversed by another correction; its amount is never
  silently edited.

Acceptance:

- The account reaches the reviewed target exactly, including concurrent-request
  and retry tests.
- Corrections change account/net balance but never income, spending, category
  totals, member balances or settlements.
- Zero-delta corrections are rejected.
- Archived accounts reject corrections until restored.
- Reason, actor, effective time, previous balance, target and delta are audited.
- Dashboard, logical activity, account history and export/restore understand the
  new movement without classifying it as cashflow.

### S2-04 — maintain non-login participants

**User story:** As the owner, I can add, rename, deactivate and restore people I
split expenses with, whether or not they ever receive a login.

Scope:

- Add participants with trimmed, case-insensitively unique active names.
- Rename with audit history.
- Deactivate only after explicit confirmation; remove inactive participants from
  new split selectors while retaining every historical split and settlement.
- Restore when no active participant has the same normalized name.
- Show access state: `No login`, `Invite pending`, `Shared access`, `Expired` or
  `Revoked`.

Acceptance:

- The owner member cannot be renamed/deactivated through participant commands.
- A participant with a non-zero shared balance cannot be deactivated; the owner
  must settle it first.
- A participant with an accepted invitation must be revoked before
  deactivation.
- Duplicate names, duplicate retries and the 20-active-participant limit fail
  with stable, human-readable errors.
- Historical screens use the current display name while audit evidence preserves
  prior names.

### S2-05 — invitation lifecycle

**User story:** As the owner, I can invite one existing participant by email,
understand the invite state, resend safely and revoke access.

Scope:

- Invite only an active non-login participant; do not create an unrelated second
  member identity from an email address.
- Add `pending`, `accepted`, `expired` and `revoked` states with created,
  expires, accepted and revoked timestamps.
- Use a 72-hour single-use acceptance link for the pilot. Persist only a token
  hash; invalidate the previous token on resend.
- Mask the email in normal UI after send. Never put an email, token or magic-link
  URL in logs, audit payloads or analytics.
- Acceptance requires authentication as the invited email and atomically links
  that profile to the existing participant row as `shared_viewer`.
- An invitee may already own a private Artha ledger. Their private ledger remains
  the default owner context, and invited spaces appear only under **Shared with
  me**.
- An invitee without a private ledger lands on the shared-only experience and is
  not forced through owner onboarding.

Acceptance:

- Only an active owner can create, resend or revoke.
- Self-invite, duplicate pending invite, wrong-email acceptance, expired token,
  reused token and already-linked participant all fail safely.
- Resend does not create a second membership; acceptance preserves the original
  member ID and historical splits.
- Revocation blocks the next request even if the viewer's auth session/JWT is
  still otherwise valid.
- Responses do not reveal whether an arbitrary email has an Artha account.
- Delivery failures are visible to the owner without leaking provider internals.

### S2-06 — shared-only authorization and read model

**User story:** As an invited person, I can understand only the expenses and
settlements involving me without seeing the owner's accounts or private ledger.

Do not grant viewers raw household-table reads. Introduce narrowly scoped,
authenticated RPC projections that derive the caller's linked member ID on the
server.

The shared-activity projection may return only:

- household display name;
- stable logical activity ID and occurred date;
- merchant/description safe for sharing, category and total transaction amount;
- the viewer's share;
- payer display name and a viewer-relative `you owe` / `owed to you` result;
- settlements involving the viewer, with amount, date and direction.

It must not return:

- account IDs, names, balances, card metadata or transfers;
- unrelated transactions or other members' split amounts;
- private notes, attachments, transaction metadata or creator identifiers;
- merchant rules, analytics, assistant context, audit events or exports.

#### Visibility matrix

| Capability/data | Owner | Non-login participant | `shared_viewer` |
| --- | --- | --- | --- |
| Private account/card balances | Full | No login | Never |
| Add/correct/archive accounts | Yes | No login | Never |
| All household transactions | Full | No login | Never |
| Relevant shared activity | Full | No login | Minimal projection only |
| Other participants and split amounts | Full | No login | Never |
| Own shared balance and relevant settlements | Full | No login | Read only |
| Create/edit transactions or settlements | Yes | No login | Never in Sprint 2 |
| Invitations and family settings | Yes | No login | Never |
| Assistant, analytics, audit and export | Yes | No login | Never |

Acceptance:

- Direct PostgREST reads by a viewer are denied for accounts, transactions,
  transfer links, full split rows, settlements, merchant rules, audit events and
  the household roster.
- The shared RPC returns a row only when the viewer is payer or has a split, and
  a settlement only when they are payer or payee.
- Guessing another household/member/activity ID returns no data, not a different
  error that confirms existence.
- Two owners and two viewers pass a complete cross-household, unrelated-row and
  revocation matrix.
- Owner behavior and existing transaction isolation remain unchanged after the
  RLS migration.

### S2-07 — invited person's mobile experience

**User story:** As a viewer, I immediately understand which household I am
viewing, what I owe/am owed and why, without private-ledger navigation.

Scope:

- Add **Shared with me** landing, relevant activity detail, balance explanation,
  invite-expired/revoked recovery and sign-out.
- Hide Home balances, Quick Add, private Transactions, Assistant, account
  settings and export routes from the viewer shell.
- A user who also owns a ledger can switch between **My ledger** and named shared
  spaces without changing permissions or mixing cached data.
- Keep Sprint 2 viewer access read-only; the owner records corrections and
  settlements.

Acceptance:

- Route guards fail closed while role/access state loads and after revocation.
- Back/forward navigation and cached requests cannot reveal the prior owner or
  another shared space.
- Empty, loading, expired, revoked, offline and API-error states are actionable.
- 320 px, 390 px and desktop pass in light and dark modes with no horizontal
  overflow; controls meet touch and keyboard accessibility requirements.

### S2-08 — release and evidence gate

Release order is always database migration, API deployment, web deployment,
then acceptance. Invitations remain disabled until all gates pass.

Required evidence:

1. Migration/catalog assertions for roles, invitations, adjustment directions,
   audit fields, constraints and grants.
2. SQL behavioral tests for owner A/owner B/viewer A/viewer B/anonymous,
   including direct-table denial and RPC projections.
3. API contract tests for every state transition, idempotency and stale balance
   correction.
4. Ledger-invariant tests proving corrections never affect income, spending or
   shared balances.
5. Web tests for settings, destructive confirmations, role routing and cache
   separation.
6. Manual 320 px, 390 px and desktop light/dark acceptance using fictional data.
7. Sanitized final-domain evidence showing invite, accept, relevant shared view,
   revoke and immediate denial. No email address or token appears in evidence.

## Delivery order and dependencies

| Order | Deliverable | Depends on | May release independently? |
| ---: | --- | --- | --- |
| 1 | Owner/settings contracts and owner-only policy hardening | Sprint 1 final-domain auth and two-owner isolation | No |
| 2 | Account/card maintenance | Owner/settings contracts | Yes, as Sprint 2A |
| 3 | Balance-correction ledger movement | Account maintenance plus logical-activity/export changes | Yes, with its invariant suite |
| 4 | Participant maintenance | Owner/settings contracts | Yes, as Sprint 2A |
| 5 | Invitation schema and lifecycle | Participant identity contract and email redirect configuration | Hidden only |
| 6 | Shared-only RPCs and RLS suite | Invitation identity link | Hidden only |
| 7 | Viewer UI and **Shared with me** context | Shared RPCs and role-aware auth bootstrap | Yes, as Sprint 2B after security gate |

## Explicitly out of Sprint 2

- Co-owner, editor or transaction-entry roles for invited users.
- Viewer-created expenses, settlements or account changes.
- Hard deletion of accounts, members or history.
- Changing an account's type/currency or rewriting its opening balance.
- Bank/card aggregation, account numbers, statement import or reconciliation.
- Arbitrary household switching as a full private ledger; Sprint 2 exposes the
  owner's ledger plus read-only shared spaces only.
- Group chat, comments, notifications beyond invitation delivery, WhatsApp and
  Telegram.
- Investments, liabilities, budgets and financial advice.

## User/provider actions at the gates

1. Before Sprint 2 begins, complete Sprint 1 final-domain login/reopen/sign-out
   and two-owner isolation acceptance.
2. Before invitation delivery is enabled, approve the invitation email copy and
   final-domain redirect in Supabase; no credential is shared in chat.
3. Provide two fictional test identities for owner/viewer isolation and one
   invitee that already owns a private ledger.
4. Review the shared projection using fictional activity and confirm that hiding
   accounts, notes and other participants matches the intended family privacy
   boundary.

## Sprint 2 definition of done

Sprint 2 is complete only when an owner can add, rename, correct, archive and
restore accounts/cards; maintain non-login participants; invite one participant;
and revoke them—while the invited person can see only their own shared facts.
All ledger totals, history and exports must remain reconstructable, every write
must be audited/idempotent, and direct database/API access must enforce the same
boundary as the UI.
