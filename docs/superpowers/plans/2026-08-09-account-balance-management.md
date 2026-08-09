# Account Balance Management Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let an authenticated owner maintain accounts/cards after onboarding and reconcile each displayed balance without rewriting opening balances or polluting income/spending.

**Architecture:** Extend ledger transactions with explicit inward/outward adjustment directions and owner-only management RPCs. FastAPI exposes validated account create/update/archive/restore/reconcile commands; React Settings renders the active and archived account list with compact mobile-first forms. Existing balance, recovery and activity projections understand adjustments, while every write remains idempotent and audited.

**Tech Stack:** Supabase PostgreSQL/RLS/RPC, FastAPI/Pydantic, React/Vite/TypeScript/Tailwind, Pytest/Vitest and SQL contract tests.

---

### Task 1: Database account-management and adjustment boundary

**Files:**
- Create: `supabase/migrations/20260809010000_account_management.sql`
- Modify: `supabase/tests/001_schema_assertions.sql`
- Modify: `supabase/tests/003_two_household_isolation.sql`
- Modify: `supabase/tests/004_recovery_round_trip.sql`

- [ ] Write SQL assertions for adjustment directions, owner-only RPC execution, balance math, income/spend exclusion and recovery round-trip.
- [ ] Run `make check-sql` and confirm the new assertions fail because the migration/RPCs do not exist.
- [ ] Add `adjustment_in`/`adjustment_out`, update balance/activity/recovery projections, and add owner-only create/update/archive/restore/reconcile RPCs.
- [ ] Ensure reconcile accepts current balance plus requested actual balance, computes the signed delta server-side, uses an idempotency key, writes an audit event and returns the updated account.
- [ ] Run `make check-sql`; expect every migration and SQL contract to parse.

### Task 2: FastAPI production and local parity

**Files:**
- Modify: `apps/api/src/artha_api/schemas.py`
- Modify: `apps/api/src/artha_api/models.py`
- Modify: `apps/api/src/artha_api/routes.py`
- Modify: `apps/api/src/artha_api/production_routes.py`
- Modify: `apps/api/src/artha_api/recovery.py`
- Modify: `apps/api/tests/test_api.py`
- Modify: `apps/api/tests/test_production_routes.py`
- Modify: `apps/api/tests/test_recovery.py`

- [ ] Add failing tests for owner account listing with archived rows, create, metadata update, archive/restore and balance reconciliation.
- [ ] Verify the tests fail with missing routes/models.
- [ ] Add strict account-management request/response models: trimmed names, immutable kind/currency/opening balance, card-only metadata and integer paise.
- [ ] Add local and production endpoints with `Idempotency-Key` on every mutation and stable 403/404/409/422 errors.
- [ ] Represent local adjustments as a ledger transaction plus ledger entry so dashboard semantics match production.
- [ ] Update recovery validation to accept adjustments only when category, payer and splits are absent.
- [ ] Run focused API tests and expect all new and existing tests to pass.

### Task 3: Typed web API adapter

**Files:**
- Modify: `apps/web/src/types.ts`
- Modify: `apps/web/src/lib/api.ts`
- Modify: `apps/web/src/lib/api.test.ts`

- [ ] Add failing adapter tests for strict managed-account mapping and mutation payloads.
- [ ] Verify the tests fail because management functions are absent.
- [ ] Add `ManagedAccount`, account create/update/reconcile inputs, mapping and API methods.
- [ ] Reject malformed responses and preserve server-safe error messages.
- [ ] Run `npm --prefix apps/web test -- src/lib/api.test.ts` and expect green.

### Task 4: Accounts & cards Settings UI

**Files:**
- Create: `apps/web/src/components/AccountManagementPanel.tsx`
- Create: `apps/web/src/components/AccountManagementPanel.test.tsx`
- Modify: `apps/web/src/pages/SettingsPage.tsx`
- Modify: `apps/web/src/pages/SettingsPage.test.tsx`

- [ ] Write failing interaction tests for loading, adding an account, editing card metadata, reconciling balance, archive/restore confirmation and recoverable errors.
- [ ] Verify tests fail because the panel is missing.
- [ ] Build three clear states: active accounts, add account, and collapsed archived accounts.
- [ ] Show bank/cash/wallet balances and credit-card outstanding/available credit; label reconciliation as `Set actual balance` with previous value, signed correction and result.
- [ ] Require a date and short reason before reconcile; never expose direct opening-balance editing.
- [ ] Refresh the list after mutation, preserve failed form input, and retain 44px targets plus light/dark responsive layouts.
- [ ] Run focused Settings tests and expect green.

### Task 5: Release documentation and safeguards

**Files:**
- Modify: `docs/PROJECT-CHECKPOINT.md`
- Modify: `docs/SPRINT-BOARD.md`
- Modify: `docs/TASKS.md`
- Modify: `docs/artifacts/architecture/v2-accounts-family-management.md`
- Create: `docs/artifacts/qa/2026-08-09-account-management-release.md`

- [ ] Mark only the shipped account-maintenance slice complete; keep participant/invitation scope open.
- [ ] Document migration order, rollback boundary and no-opening-balance-rewrite invariant.
- [ ] Record automated evidence without real account names, balances or user identifiers.
- [ ] Run `python3 scripts/check_docs_links.py` and expect all links valid.

### Task 6: Integration, deployment and authenticated acceptance

**Files:**
- No new implementation files.

- [ ] Run fresh `make check`; require lint, types, all web/API tests, build, SQL parsing and AI contracts to pass.
- [ ] Apply the migration to the exact linked Artha Supabase project and reload the PostgREST schema.
- [ ] Deploy API before web, then verify both final aliases return healthy responses.
- [ ] On the final domain, use fictional values to create an account, edit a card, reconcile a balance, reload, verify dashboard movement, then archive/restore where allowed.
- [ ] Verify reconciliation changes available balance but not income, spending or shared totals; verify duplicate submission is idempotent.
- [ ] Sweep Settings at 320px, 390px and desktop in light/dark with no overflow or console errors.
- [ ] Commit, push, merge to `main`, verify GitHub CI/CodeQL and exact production deployment SHA before reporting completion.
