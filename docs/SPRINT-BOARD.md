# Artha sprint board

Start with [`PROJECT-CHECKPOINT.md`](PROJECT-CHECKPOINT.md) for the current
handoff, release guard and exact resume sequence.

Updated: 7 August 2026
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
| Persistent production login | Deployed; acceptance pending | Expired, reused, wrong-browser and stale-session states are live; final-domain user acceptance remains |
| Server-owned onboarding/profile | Deployed; acceptance pending | Profile, household and members hydrate from the server; final-domain cross-device acceptance remains |
| ₹25k self-transfer flow | Deployed | Parser, review UI, atomic backend and history projection are live; authenticated smoke remains |
| First-request reliability | Deployed | API now runs Mumbai → Mumbai; authenticated cold/warm measurement remains |
| Structured Gemini features | Release candidate | Capture 50/50, auto-tag 30/30 and assistant 24/24 fictional hosted gates passed; production variables are configured and deployment verification is next |
| Parser evaluation dataset | Done | 50 fictional cases plus an automated contract checker are in the repository |
| Private AI learning/eval ledger | Priority next | Audited private interactions, user corrections, token budgets and eval runs need RLS-backed storage, export/delete controls and sanitized dataset promotion |
| Accounts & family | Next implementation track | Product contract and secure architecture are complete; owner maintenance ships before invitations |
| Family email invitations | Sprint 2B | Permission model is defined; owner-only RLS hardening must land before any invited viewer |
| Account-specific history | Done locally | The ledger filters banks/cards and includes both sides of a transfer |
| Accounts/cards management after onboarding | Backlog | Detailed V2 settings task is recorded |
| Production acceptance | Blocked | Requires two test identities plus login/link interaction from the user |

## Sprint 1 — trust and capture foundation

### Authentication and onboarding

- [ ] Verify magic-link callback on the final domain in the same browser.
- [ ] Verify session survives refresh, tab close and browser reopen.
- [x] Replace local-only profile hydration with a server profile/household endpoint.
- [x] Hydrate an existing user's display name, household and participants from the server after setup lookup.
- [x] Clarify login copy: the same email action creates a first account or signs in a returning user.
- [ ] Prove on the final domain that an existing user never repeats onboarding on another device.
- [x] Add explicit callback, expired-link and wrong-browser recovery states.
- [ ] Verify sign-out clears the local session but never deletes ledger data.

### Natural-language capture and transfers

- [x] Parse `25k` as ₹25,000 and Indian lakh shorthand as rupees, then store integer paise.
- [x] Resolve ordered source and destination accounts from `ICICI -> HDFC`.
- [x] Render separate **Transfer from** and **Transfer to** review controls.
- [x] Prevent family splits and same-account confirmation for transfers.
- [x] Confirm transfers through the atomic, idempotent Supabase `create_transfer` RPC.
- [x] Keep total balance, income and spending unchanged for internal transfers.
- [x] Collapse paired transfer rows into one production history movement with zero cashflow.
- [x] Replace raw-row prefix pagination with a logical ledger activity projection so a transfer pair cannot be split at a page boundary.
- [x] Add an account activity filter that includes both the source and destination side of transfers.
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
- [x] Add a truthful offline/network-state banner without claiming that V1 queues writes.
- [ ] Add sanitized authenticated cold/warm latency evidence.

### Structured LLM parsing and evaluation

- [x] Define a strict provider-neutral capture schema for kind, paise, accounts, category, members and date.
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
- [x] Add a hosted-model evaluation runner with field/outcome/tag slices and sanitized reports.
- [x] Preserve the Qwen/Groq baseline as historical provider evidence.
- [x] Add Gemini through the official server-side SDK with `store=false` and deterministic fallback.
- [x] Separate HTTP/rate-limit/timeout/schema/grounding failures from model correctness without persisting private text.
- [x] Respect `Retry-After`, back off safely, checkpoint progress and resume unfinished cases.
- [x] Pass the hosted fictional gates: capture 50/50, auto-tag 30/30 and assistant 24/24.
- [ ] Verify the deployed production API reports Gemini and completes one fictional request for each feature path.

## Sprint 2 — Accounts & family

**Entry gate:** Sprint 1 login/session, two-household isolation and transfer
smoke tests pass on the final domain.

Detailed acceptance criteria and security decisions live in
[`artifacts/architecture/sprint-2-accounts-family-contract.md`](artifacts/architecture/sprint-2-accounts-family-contract.md)
and [`artifacts/architecture/v2-accounts-family-management.md`](artifacts/architecture/v2-accounts-family-management.md).

### Sprint 2A — owner maintenance

| ID | Status | Task | Depends on | Acceptance gate |
| --- | --- | --- | --- | --- |
| S2-01 | Next | Owner-only **Accounts & family** settings snapshot and responsive route | Sprint 1 production acceptance | Returning owner sees active/archived server data; non-owner gets `403` |
| S2-02 | Planned | Add, rename, archive and restore banks, cash, wallets and cards | S2-01 | Immutable type/currency, duplicate-name and non-zero/archive rules pass |
| S2-03 | Planned | Update card limit, statement day and due day | S2-02 | Card-only validation and over-limit warning pass |
| S2-04 | Planned | Audited balance correction using append-only adjustment movements | S2-02 | Balance changes exactly; income/spend/splits remain unchanged |
| S2-05 | Planned | Add, rename, deactivate and restore non-login participants | S2-01 | Historical splits survive; unsettled people cannot be deactivated |

### Sprint 2B — family access

| ID | Status | Task | Depends on | Acceptance gate |
| --- | --- | --- | --- | --- |
| S2-06 | Planned | Harden base-table RLS/RPCs to owner-only before adding viewers | S2-01 | Direct viewer reads of accounts, ledger, roster and audit are denied |
| S2-07 | Planned | Invitation create/resend/expire/accept/revoke lifecycle | S2-05, S2-06 | Token hash, email match, single-use acceptance and immediate revocation pass |
| S2-08 | Planned | **Shared with me** minimal read model and mobile UI | S2-07 | Viewer sees only their shared expenses/settlements, never private balances |
| S2-09 | Planned | Two-owner/two-viewer production isolation and revocation matrix | S2-08 | Cross-household and unrelated-row probes return no data |

### Sprint 2C — private capture learning loop

| ID | Status | Task | Depends on | Acceptance gate |
| --- | --- | --- | --- | --- |
| S2-10 | Planned | Store private capture feedback: original text, parser/model/version, proposed JSON and user-confirmed JSON | Privacy/schema review | Enabled by default with clear onboarding disclosure; never written before review |
| S2-11 | Planned | Add Settings toggle plus export and delete-all controls | S2-10 | Household can disable, export and permanently remove learning history |
| S2-12 | Planned | Promote reviewed, sanitized examples into versioned eval cases | S2-10 | No automatic external training or public dataset use without separate consent |
| S2-13 | Priority next | Add token-budget scheduler and per-case checkpoints for capture, auto-tagging and assistant evals | Hosted benchmark evidence | RPM/RPD/TPM/TPD headers are respected; unfinished cases resume without repeated completed calls |
| S2-14 | Priority next | Add RLS-backed `ai_interactions` and append-only `ai_interaction_reviews` audit tables | Privacy contract | Only the owning household can read/export/delete; no keys, provider prose or account numbers are stored |
| S2-15 | Planned | Add `model_eval_runs` and `model_eval_cases` with versioned model/prompt/schema metadata | S2-13 | Every benchmark and failure is queryable without storing private input text |

Detailed schema and privacy rules: [`artifacts/architecture/private-ai-learning-eval-ledger.md`](artifacts/architecture/private-ai-learning-eval-ledger.md).

## Sprint 3 — recovery, production quality and measured AI

### Recovery and corrections

- [x] Define a versioned export bundle with schema version and checksums.
- [x] Add client-side encrypted export; the passphrase never reaches Artha.
- [x] Restore first into a new or empty household with a full preview and atomic validation.
- [ ] Add correction, soft-delete, settlement and dedicated per-account activity UI.
- [x] Prove restored balances, transfers, splits and audit facts match in local SQL round-trip acceptance.
- [ ] Repeat the encrypted export/restore drill with fictional data on the final domain.

### Production quality

- [x] Add Vercel Web Analytics and Speed Insights with query/fragment redaction tests.
- [ ] Record cold/warm authenticated latency after the Mumbai deployment.
- [ ] Add privacy-first Sentry error monitoring after explicit approval: error events only, no Session Replay, financial payloads, emails or IP collection, with client/server redaction tests.
- [ ] Add a deliberate per-user rate-limit policy.
- [x] Add no-store API caching policy and web/API security headers locally.
- [ ] Verify deployed security headers and record sanitized log-redaction evidence.
- [ ] Test PWA install/reopen, offline unsaved drafts, expired auth and accessibility.
- [ ] Complete the 320 px, 390 px and desktop light/dark matrix.

Current local evidence: Home passes at 320 px; Home, Transactions, Shared,
Assistant and Quick Add pass at 390 px with no horizontal overflow. Quick Add
passes visual light/dark review, and Home passes visual mobile plus 1440 px dark
review. Onboarding and auth recovery still need the full final-domain matrix.
See [`artifacts/qa/2026-08-06-web-interface-guidelines-audit.md`](artifacts/qa/2026-08-06-web-interface-guidelines-audit.md).

### Measured AI

- [x] Add deterministic and hosted-model scoring runners for the 50-case dataset.
- [ ] Publish separate amount/date/account/transfer/split/Hinglish error slices.
- [x] Select hosted Gemini for fictional pilot traffic after all critical-field gates pass.
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
3. Production Gemini variables are configured. Save the key in the ignored local
   `.env` only if local hosted evaluation is required; never commit it.

## Completion update format

Every finished item is reported as:

1. **Done:** the user-visible outcome.
2. **How it works:** the important product and technical behavior.
3. **Where:** links to code, tests and artifacts.
4. **Verified:** exact tests and production checks.
5. **Next:** the first remaining board item.
