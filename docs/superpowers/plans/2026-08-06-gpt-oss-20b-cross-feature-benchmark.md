# GPT-OSS 20B Cross-Feature Benchmark Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make GPT-OSS 20B the candidate for every hosted AI path, benchmark capture, tagging and assistant behavior with fictional fixtures, and publish an evidence-based adopt or reject decision.

**Architecture:** Keep `LocalFinancialAssistant` as the single provider adapter and add a strict Groq JSON-schema helper shared by its three outputs. Extend the existing sanitized capture evaluator with separate tag and assistant datasets and a cross-feature decision runner; provider availability stays separate from model correctness.

**Tech Stack:** Python 3.13, Pydantic v2, HTTPX, pytest, Groq OpenAI-compatible API, JSONL fixtures, Markdown/JSON reports.

---

### Task 1: GPT-OSS 20B default and strict response envelopes

**Files:**
- Modify: `apps/api/src/artha_api/assistant.py`
- Modify: `apps/api/tests/test_assistant.py`

- [ ] Add a failing settings test asserting both dataclass and environment defaults use `openai/gpt-oss-20b`.
- [ ] Add failing request-shape tests asserting all three Groq calls send `response_format.type=json_schema`, `strict=true`, a named schema, no tools, and `reasoning_effort=none`.
- [ ] Run `cd apps/api && uv run pytest tests/test_assistant.py -q` and confirm the new expectations fail against the Qwen/JSON-object implementation.
- [ ] Add `DEFAULT_GROQ_MODEL`, a strict-schema response-format helper, and a capture response envelope so all Groq schemas have an object root.
- [ ] Parse the capture envelope, retain Pydantic validation and run existing allow-list grounding unchanged.
- [ ] Run `cd apps/api && uv run pytest tests/test_assistant.py -q` and confirm all assistant tests pass.
- [ ] Commit only Task 1 files with `git commit -m "Use GPT-OSS 20B strict outputs"`.

### Task 2: Versioned auto-tagging benchmark

**Files:**
- Create: `evals/tag-context-v1.json`
- Create: `evals/tag-suggestions-v1.jsonl`
- Create: `apps/api/src/artha_api/tag_evals.py`
- Create: `apps/api/tests/test_tag_evals.py`
- Modify: `Makefile`
- Modify: `evals/README.md`

- [ ] Write failing loader tests for unique IDs, valid directions, allow-listed expected IDs, null expectations for ambiguous/unknown cases, and a minimum 30-case suite.
- [ ] Write failing scorer tests for exact category matching, safe null suggestions, invented IDs, provider-unavailable separation and sanitized output.
- [ ] Run `cd apps/api && uv run pytest tests/test_tag_evals.py -q` and confirm the module is missing.
- [ ] Implement typed loader, sequential hosted evaluator, bounded retry/checkpoint behavior, field/tag slices, latency timing and sanitized JSON/Markdown output.
- [ ] Add at least 30 fictional cases spanning clear merchants/descriptions, aliases, income/expense boundaries, ambiguity, unknowns, Hinglish and prompt injection.
- [ ] Add `eval-tag-validate` and `eval-tag-hosted` Make targets.
- [ ] Run the focused tests and validation target; confirm no key or hosted request is needed for validation.
- [ ] Commit Task 2 files with `git commit -m "Add auto-tagging model benchmark"`.

### Task 3: Versioned assistant and generative-UI benchmark

**Files:**
- Create: `evals/assistant-context-v1.json`
- Create: `evals/assistant-questions-v1.jsonl`
- Create: `apps/api/src/artha_api/assistant_evals.py`
- Create: `apps/api/tests/test_assistant_evals.py`
- Modify: `Makefile`
- Modify: `evals/README.md`

- [ ] Write failing loader tests for allowed intents/widgets, expected deterministic values and a minimum 24-case suite.
- [ ] Write failing scorer tests for intent, widget type, expected values, arbitrary component rejection, write-attempt refusal and sanitized reports.
- [ ] Run `cd apps/api && uv run pytest tests/test_assistant_evals.py -q` and confirm the module is missing.
- [ ] Implement typed loader, sequential hosted evaluator, bounded retry/checkpoint behavior, intent/widget/value/safety slices, latency timing and sanitized reports.
- [ ] Add a fixed fictional context and at least 24 questions across summary, spending, income, cashflow, shared, transactions, ambiguity, unsupported requests and attempted writes.
- [ ] Add `eval-assistant-validate` and `eval-assistant-hosted` Make targets.
- [ ] Run focused tests and validation; confirm financial values are compared to fixture values rather than model prose.
- [ ] Commit Task 3 files with `git commit -m "Add assistant model benchmark"`.

### Task 4: Cross-feature decision report

**Files:**
- Create: `apps/api/src/artha_api/model_decision.py`
- Create: `apps/api/tests/test_model_decision.py`
- Modify: `Makefile`
- Modify: `docs/DECISIONS.md`
- Modify: `docs/SPRINT-BOARD.md`

- [ ] Write failing tests for adopt, conditional-pilot and reject decisions using the thresholds in the approved design.
- [ ] Run `cd apps/api && uv run pytest tests/test_model_decision.py -q` and confirm the module is missing.
- [ ] Implement a report reader that validates model identity, dataset versions and freshness, then emits sanitized JSON/Markdown with every gate and its evidence.
- [ ] Add `eval-model-validate`, `eval-model-hosted`, and `eval-model-decide` targets.
- [ ] Update documentation only from the generated decision; never claim adoption from a partial run.
- [ ] Run focused tests and offline validation.
- [ ] Commit Task 4 files with `git commit -m "Add cross-feature model decision gate"`.

### Task 5: Hosted run and release verification

**Files:**
- Generate: `evals/reports/capture-model-<timestamp>.json` and `.md`
- Generate: `evals/reports/tag-model-<timestamp>.json` and `.md`
- Generate: `evals/reports/assistant-model-<timestamp>.json` and `.md`
- Generate: `docs/artifacts/qa/2026-08-06-gpt-oss-20b-decision.md`

- [ ] Load the existing server-side Groq key without printing it and confirm model availability.
- [ ] Run the three suites sequentially with checkpointing and provider pacing; resume unavailable cases instead of restarting completed cases.
- [ ] Run the decision target and inspect every hard gate, failure slice and unavailable category.
- [ ] Run `make check` and confirm lint, typing, all web/API tests, production build, SQL parsing and all offline validators pass.
- [ ] Confirm `git diff --check`, scan reports for keys/free text/real identifiers, and inspect `git status --short`.
- [ ] Commit sanitized datasets, implementation, tests and reviewed reports; do not commit checkpoints or secrets.
- [ ] Report the measured outcome as adopt, conditional pilot or reject. Do not deploy or enable production hosted AI without separate approval.
