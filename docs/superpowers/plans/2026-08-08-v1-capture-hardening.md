# V1 Capture Hardening Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close the current V1 manual-recovery, category-grounding, account-loading and AI-disclosure gaps before final fictional-pilot acceptance.

**Architecture:** Expose one authenticated, read-only capture-context endpoint containing the owner's active accounts and direction-valid household categories. Quick Add uses that context for manual and AI-draft correction, retains exact source text through errors, and never writes before explicit confirmation; Settings explains the current Gemini data boundary without collecting new telemetry.

**Tech Stack:** FastAPI, Pydantic, Supabase REST adapter, React 19, TypeScript, Vitest, pytest

---

### Task 1: Add an authenticated capture-context contract

**Files:**
- Modify: `apps/api/src/artha_api/schemas.py`
- Modify: `apps/api/src/artha_api/routes.py`
- Modify: `apps/api/src/artha_api/production_routes.py`
- Modify: `apps/api/tests/test_api.py`
- Modify: `apps/api/tests/test_production_routes.py`

- [ ] Add response models for accounts and categories where category kind is exactly `expense`, `income`, or `both`.
- [ ] Add `GET /api/v1/capture-context` to local/demo and production routers; require the existing authenticated owner/household boundary.
- [ ] Return active accounts and categories from server-owned records; do not accept client-supplied IDs or names.
- [ ] Test authentication, household scoping, category kinds, archived filtering and an empty-list response.
- [ ] Run focused API tests and commit with `feat: expose grounded capture context`.

### Task 2: Make manual recovery complete and safe

**Files:**
- Modify: `apps/web/src/types.ts`
- Modify: `apps/web/src/lib/api.ts`
- Modify: `apps/web/src/lib/api.test.ts`
- Modify: `apps/web/src/pages/QuickAddPage.tsx`
- Modify: `apps/web/src/pages/QuickAddPage.test.tsx`

- [ ] Add the typed capture-context adapter and failing mapping/error tests.
- [ ] Replace the initial accounts-only fetch with capture-context loading and an accessible loading/error state.
- [ ] Preserve capture text and draft fields when context loading fails; provide a visible **Try again** action and explain why confirmation is disabled.
- [ ] Add a manual transaction-type control for Expense, Income and Transfer.
- [ ] When type changes, clear invalid splits/destination fields and select only a direction-valid category; transfers always use `Transfer` and require different source/destination accounts.
- [ ] Replace free-text category correction with a server-owned select filtered to `expense|both` for expenses and `income|both` for income.
- [ ] Keep AI-selected categories visible only when they match the server allow-list; otherwise require a valid selection before confirmation.
- [ ] Test exact-text recovery for each type, direction filtering, type switching, account retry, context-unavailable confirmation guard, transfer rules and no write before confirmation.
- [ ] Run focused web tests and commit with `feat: harden manual capture recovery`.

### Task 3: Add the fictional-pilot AI data-use notice

**Files:**
- Modify: `apps/web/src/pages/SettingsPage.tsx`
- Create or modify: `apps/web/src/pages/SettingsPage.test.tsx`

- [ ] Add a concise Settings section stating that natural-language capture and Ask Artha send the submitted fictional text/question plus bounded household context to configured Gemini through the Artha server.
- [ ] State that Gemini cannot write to the ledger, every capture requires review/confirmation, and real family-finance text is not approved during the fictional pilot.
- [ ] State that Vercel analytics receives no financial text, amounts, emails, account/member names or assistant questions.
- [ ] Test that the disclosure and fictional-data restriction are visible and accessible.
- [ ] Run focused tests and commit with `docs: add in-product AI data notice`.

### Task 4: Integrate and verify

**Files:**
- Modify: `docs/PROJECT-CHECKPOINT.md`
- Modify: `docs/SPRINT-BOARD.md`
- Modify: `docs/TASKS.md`
- Modify: `docs/artifacts/qa/v1-scenario-matrix.md`
- Modify: `docs/DEPLOYMENT.md`

- [ ] Mark PA-01, PA-02, PA-04 and PA-05 complete only after their tests pass.
- [ ] Correct stale deployment, CI, migration-count and AI-primary status claims using PR #20 / merge `69e44a8` evidence.
- [ ] Keep two-owner isolation, final-domain restore, log redaction, browser-process persistence, real provider-unavailable acceptance and fresh hosted eval rerun open.
- [ ] Add the AI validation commands to `.github/workflows/ci.yml` so CI matches `make check`.
- [ ] Run `make check`, inspect `git diff --check`, and commit with `docs: record V1 hardening and deployed release`.
