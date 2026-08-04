# Artha sprint board

Updated: 4 August 2026  
Goal: make the private pilot trustworthy before entering real financial data

Current scope: a private personal ledger with expense splitting for friends and
family. Separate logins for invited people are optional future work, not a
Sprint 1 dependency.

## How to read this board

- **Done** means implemented, tested and documented.
- **In progress** means code or verification is actively underway.
- **Blocked** means a named user or provider action is required.
- **Next** is ordered; the first unchecked item is the next engineering task.

## Current snapshot

| Area | Status | What this means |
| --- | --- | --- |
| Public repository and CI | Done | GitHub, CI and CodeQL are active |
| Vercel and Supabase infrastructure | Done | Web, API and database are live on personal accounts |
| Persistent production login | In progress | Magic-link callback and reopen behavior still need final-domain acceptance |
| Server-owned onboarding/profile | Done locally | Profile, household and members now hydrate from the server; final-domain acceptance remains |
| ₹25k self-transfer flow | Deployed | Parser, review UI, atomic backend and history projection are live; authenticated smoke remains |
| First-request reliability | Deployed | API now runs Mumbai → Mumbai; authenticated cold/warm measurement remains |
| Structured Qwen capture | Done locally | Strict schema and allow-list grounding pass tests; provider key and benchmark remain |
| Parser evaluation dataset | Done | 50 fictional cases plus an automated contract checker are in the repository |
| Family email invitations | Next | Permission model is defined; schema, RLS, email acceptance and limited UI remain |
| Accounts/cards management after onboarding | Backlog | Detailed V2 task is recorded |
| Production acceptance | Blocked | Requires two test identities plus login/link interaction from the user |

## Sprint 1 — trust and capture foundation

### Authentication and onboarding

- [ ] Verify magic-link callback on the final domain in the same browser.
- [ ] Verify session survives refresh, tab close and browser reopen.
- [x] Replace local-only profile hydration with a server profile/household endpoint.
- [x] Hydrate an existing user's display name, household and participants from the server after setup lookup.
- [x] Clarify login copy: the same email action creates a first account or signs in a returning user.
- [ ] Prove on the final domain that an existing user never repeats onboarding on another device.
- [ ] Add explicit callback, expired-link and wrong-browser recovery states.
- [ ] Verify sign-out clears the local session but never deletes ledger data.

### Natural-language capture and transfers

- [x] Parse `25k` as ₹25,000 and Indian lakh shorthand as rupees, then store integer paise.
- [x] Resolve ordered source and destination accounts from `ICICI -> HDFC`.
- [x] Render separate **Transfer from** and **Transfer to** review controls.
- [x] Prevent family splits and same-account confirmation for transfers.
- [x] Confirm transfers through the atomic, idempotent Supabase `create_transfer` RPC.
- [x] Keep total balance, income and spending unchanged for internal transfers.
- [x] Collapse paired transfer rows into one production history movement with zero cashflow.
- [ ] Replace raw-row prefix pagination with a logical ledger activity projection so a transfer pair cannot be split at a page boundary.
- [ ] Add dedicated per-account activity views (history already names both accounts).
- [x] Run the full local web/API test and production-build gate.
- [ ] Run the production smoke test after deployment.

### Runtime reliability

- [x] Identify Vercel Washington-to-Supabase Mumbai region mismatch.
- [x] Configure the Python API for Vercel Mumbai (`bom1`) with Fluid compute.
- [x] Increase the browser API timeout from 3.5 seconds to 10 seconds.
- [x] Retry transient reads and explicitly idempotent writes once.
- [x] Never retry an unsafe onboarding write automatically.
- [ ] Deploy and measure cold plus warm authenticated requests.
- [x] Verify the deployed API executes in Mumbai (`bom1`) beside Supabase.
- [ ] Add sanitized latency evidence and a user-friendly network-state UI.

### Structured LLM parsing and evaluation

- [x] Define a strict Qwen capture schema for kind, paise, accounts, category, members and date.
- [x] Ground every model-selected ID against server-provided allow-lists.
- [x] Reject invented account, category or member IDs.
- [x] Represent `draft`, `clarify` and `reject` as separate model outcomes.
- [x] Surface model warnings and never label a warned draft “Looks good”.
- [x] Reuse one idempotency key when the user retries the same reviewed draft.
- [x] Keep model output advisory and review-before-write.
- [x] Finish the production parsing endpoint regression tests.
- [x] Add 50 fictional evaluation cases across English, Hinglish, typos and ambiguity.
- [x] Validate dataset IDs, allow-listed entities, outcomes and integer-paise values in CI.
- [x] Gate 22 common/safety-critical deterministic drafts plus negative, ambiguous and unknown-member input.
- [ ] Add the hosted-model evaluation runner and score all 50 cases.
- [ ] Configure the server-only Groq key after the user creates one.
- [ ] Run the benchmark and publish accuracy/error slices before enabling Qwen.

## Sprint 2 — collaborative household access

**Entry gate:** Sprint 1 login/session, two-household isolation and transfer
smoke tests pass on the final domain.

**Scope note:** optional for the current personal pilot. V1 already supports
non-login friends/family participants for splits.

### Invitation and permission model

- [x] Separate non-login participants from authenticated invited users in the product model.
- [x] Define the first invited role as limited `shared_viewer`.
- [ ] Add invitation, acceptance, expiry, resend and revocation tables/functions.
- [ ] Add audited owner-only invitation APIs.
- [ ] Add RLS proving a shared viewer cannot read account balances or unrelated transactions.
- [ ] Link an accepted identity to exactly one participant record.
- [ ] Build owner invitation management UI with email and status.
- [ ] Build the invited user's limited shared-expense and settlement UI.
- [ ] Add two-owner/two-viewer isolation and revocation tests.

### Post-onboarding management

- [ ] Add **Accounts & family** settings.
- [ ] Add/rename/archive banks, cash, wallets and cards.
- [ ] Update card limits, statement days and due days.
- [ ] Add/rename/deactivate non-login participants.
- [ ] Record balance corrections as audited adjustments, never history rewrites.

## Sprint 3 — recovery, production quality and measured AI

### Recovery and corrections

- [ ] Define a versioned export bundle with schema version and checksums.
- [ ] Add client-side encrypted export; the passphrase never reaches Artha.
- [ ] Restore first into a new or empty household with a full preview and atomic validation.
- [ ] Add correction, soft-delete, settlement and dedicated per-account activity UI.
- [ ] Prove restored balances, transfers, splits and audit facts match the source ledger.

### Production quality

- [ ] Record cold/warm authenticated latency after the Mumbai deployment.
- [ ] Add rate limits, security headers and log-redaction evidence.
- [ ] Test PWA install/reopen, offline unsaved drafts, expired auth and accessibility.
- [ ] Complete the 320 px, 390 px and desktop light/dark matrix.

### Measured AI

- [ ] Add deterministic and hosted-model scoring runners for the 50-case dataset.
- [ ] Publish separate amount/date/account/transfer/split/Hinglish error slices.
- [ ] Enable hosted Qwen only if the agreed critical-field thresholds pass.
- [ ] Show assistant evidence range, source count and matching transactions.
- [ ] Prove assistant totals equal deterministic database calculations.

## Sprint 4 — optional channels and net-worth foundation

### Messaging capture (independent release gate)

- [ ] Define a provider-neutral message → authenticated unsaved draft → PWA review link flow.
- [ ] Pilot Telegram first; reassess current WhatsApp pricing and account requirements before committing.
- [ ] Verify webhook signatures, sender mapping, replay protection, rate limits and consent.
- [ ] Never confirm a ledger write from a message alone.

### Investments and liabilities (independent release gate)

- [ ] Model investment accounts, instruments, holdings/lots, liabilities and dated prices.
- [ ] Start with manual entry and CSV import; defer bank/broker aggregation.
- [ ] Keep portfolio transfers separate from spending and show valuation timestamps.
- [ ] Reconcile holdings from transactions and prevent net-worth double counting.
- [ ] Defer trading, advice, tax calculations and automatic corporate actions.

## Release blockers before real financial data

- [ ] Final-domain login, refresh, reopen and sign-out pass.
- [ ] Two independent owners cannot read or write each other's households.
- [ ] Four banks, multiple cards, a transfer, a backdated expense and a family split pass end to end.
- [ ] 320 px, 390 px and desktop pass in light and dark modes.
- [ ] Browser/API logs contain no tokens or financial payloads.
- [ ] Security headers are enabled and verified.
- [ ] Encrypted export/restore reconstructs the ledger successfully.

## Actions needed from the user

1. Complete one final-domain sign-in link in the same browser that requested it.
2. Provide a second test email identity for isolation testing; do not share passwords or email tokens.
3. Create a Groq API key when ready; enter it directly in Vercel, never in chat or source control.

## Completion update format

Every finished item is reported as:

1. **Done:** the user-visible outcome.
2. **How it works:** the important product and technical behavior.
3. **Where:** links to code, tests and artifacts.
4. **Verified:** exact tests and production checks.
5. **Next:** the first remaining board item.
