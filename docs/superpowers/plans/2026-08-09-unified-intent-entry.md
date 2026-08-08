# Unified Intent Entry Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let either natural-language composer route a money event to the existing unsaved Quick Add review or a ledger question directly into the existing Ask Artha conversation.

**Architecture:** Add one authenticated, strict Gemini classification endpoint with four possible outcomes and no database context or write authority. A focused React composer owns routing/recovery, while Quick Add and Ask Artha remain the only owners of capture and analytics behavior. Router history state carries a one-time assistant handoff and is consumed before the existing chat request runs.

**Tech Stack:** Python 3.13, FastAPI, Pydantic v2, Google Gemini Interactions API, React 19, TypeScript, Vite, Vitest, Testing Library and pytest.

---

## File structure

- Create `apps/api/src/artha_api/intent_router.py`: strict router enums, schemas, prompt and response contract.
- Modify `apps/api/src/artha_api/assistant.py`: provider call that returns a validated router result.
- Create `apps/api/src/artha_api/intent_routes.py`: authenticated environment-independent endpoint and sanitized failure response.
- Modify `apps/api/src/artha_api/app.py`: mount intent routes in local and production applications.
- Create `apps/api/tests/test_intent_router.py`: schema, prompt, provider and endpoint contract tests.
- Modify `apps/web/src/lib/api.ts`: strict `routeIntent` adapter.
- Modify `apps/web/src/types.ts`: browser-facing routed-intent types.
- Create `apps/web/src/components/UnifiedEntryComposer.tsx`: routing/loading/clarification component.
- Create `apps/web/src/components/UnifiedEntryComposer.test.tsx`: routing and recovery interaction tests.
- Modify `apps/web/src/pages/HomePage.tsx` and its test: universal copy and destination handoff.
- Modify `apps/web/src/pages/QuickAddPage.tsx` and its test: route before capture while preserving manual entry.
- Modify `apps/web/src/pages/AssistantPage.tsx` and its test: consume and submit a question exactly once.
- Create `evals/intent-router-cases.jsonl`: fictional balanced routing dataset.
- Modify `apps/api/src/artha_api/feature_evals.py` and its tests: keyless dataset validation and hosted runner.
- Modify `docs/product-requirements.md`, `docs/system-architecture.md`, `docs/PROJECT-CHECKPOINT.md`, `docs/SPRINT-BOARD.md` and `README.md`: current behavior and release evidence.

### Task 1: Strict router domain and Gemini boundary

**Files:**
- Create: `apps/api/src/artha_api/intent_router.py`
- Modify: `apps/api/src/artha_api/assistant.py`
- Test: `apps/api/tests/test_intent_router.py`

- [ ] **Step 1: Write failing schema and provider tests**

Cover exact enum values, whitespace-normalized input, blank/overlength rejection,
extra-field rejection, prompt-injection input treated as data, valid Gemini JSON,
invalid model intent and disabled-provider failure.

```python
def test_router_result_is_a_closed_enum() -> None:
    assert IntentRouteResult(intent="ask_ledger").intent is UnifiedIntent.ASK_LEDGER
    with pytest.raises(ValidationError):
        IntentRouteResult.model_validate({"intent": "delete_ledger"})

async def test_gemini_router_returns_only_the_validated_intent() -> None:
    assistant, interactions = gemini_assistant('{"intent":"capture_transaction"}')
    response = await assistant.route_intent("Paid 850 at Zomato")
    assert response.result.intent is UnifiedIntent.CAPTURE_TRANSACTION
    assert interactions.last_body["store"] is False
```

- [ ] **Step 2: Run the focused tests and verify RED**

Run:

```bash
cd apps/api && uv run pytest tests/test_intent_router.py -q
```

Expected: collection fails because `artha_api.intent_router` and
`LocalFinancialAssistant.route_intent` do not exist.

- [ ] **Step 3: Implement the strict router types and prompt**

```python
class UnifiedIntent(StrEnum):
    CAPTURE_TRANSACTION = "capture_transaction"
    ASK_LEDGER = "ask_ledger"
    CLARIFY = "clarify"
    UNSUPPORTED = "unsupported"

class IntentRouteResult(RouterStrictModel):
    intent: UnifiedIntent

class IntentRouteResponse(RouterStrictModel):
    provider: Literal[LlmProvider.GEMINI]
    model: str = Field(min_length=1, max_length=80)
    mode: Literal["model"] = "model"
    result: IntentRouteResult
```

The prompt must classify statements of new money events as capture, historical
questions as ledger questions, fragments as clarification and unrelated/advice
requests as unsupported. It must request no explanation or reasoning.

- [ ] **Step 4: Implement the Gemini call in `LocalFinancialAssistant`**

Use `_gemini_interaction` with `IntentRouteResult.model_json_schema()`, minimal
thinking, `store=False` and the existing timeout. Do not add a deterministic
fallback and do not load financial context.

- [ ] **Step 5: Run focused tests and static checks**

```bash
cd apps/api && uv run pytest tests/test_intent_router.py -q
cd apps/api && uv run ruff check src/artha_api/intent_router.py src/artha_api/assistant.py tests/test_intent_router.py
cd apps/api && uv run mypy
```

Expected: all pass.

- [ ] **Step 6: Commit the router domain**

```bash
git add apps/api/src/artha_api/intent_router.py apps/api/src/artha_api/assistant.py apps/api/tests/test_intent_router.py
git commit -m "feat: add bounded Gemini intent router"
```

### Task 2: Authenticated route endpoint

**Files:**
- Create: `apps/api/src/artha_api/intent_routes.py`
- Modify: `apps/api/src/artha_api/app.py`
- Test: `apps/api/tests/test_intent_router.py`

- [ ] **Step 1: Write failing endpoint tests**

Test authentication, exact success JSON, blank and overlength 422 responses,
sanitized 503 when the provider is disabled and absence of any Supabase client
dependency.

```python
async def test_intent_route_returns_a_strict_model_response(client, monkeypatch):
    monkeypatch.setattr(LocalFinancialAssistant, "route_intent", fake_ask_route)
    response = await client.post(
        "/api/v1/intents/route",
        headers={"Authorization": "Bearer demo"},
        json={"message": "Show my last three months"},
    )
    assert response.json()["result"] == {"intent": "ask_ledger"}
```

- [ ] **Step 2: Run endpoint test and verify RED**

```bash
cd apps/api && uv run pytest tests/test_intent_router.py -q
```

Expected: 404 for the new route.

- [ ] **Step 3: Add the shared authenticated router**

```python
router = APIRouter(prefix="/api/v1/intents", tags=["assistant"])

@router.post("/route", response_model=IntentRouteResponse)
async def route_intent(payload: IntentRouteRequest, _auth: AuthDependency) -> IntentRouteResponse:
    try:
        return await LocalFinancialAssistant().route_intent(payload.message)
    except AssistantUnavailableError as error:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "AI routing is temporarily unavailable; nothing was saved.",
        ) from error
```

Mount this router once for both application modes.

- [ ] **Step 4: Run endpoint and production-boundary tests**

```bash
cd apps/api && uv run pytest tests/test_intent_router.py tests/test_auth.py tests/test_production_routes.py -q
```

Expected: all pass.

- [ ] **Step 5: Commit the API endpoint**

```bash
git add apps/api/src/artha_api/intent_routes.py apps/api/src/artha_api/app.py apps/api/tests/test_intent_router.py
git commit -m "feat: expose authenticated intent routing"
```

### Task 3: Strict web adapter and reusable composer

**Files:**
- Modify: `apps/web/src/types.ts`
- Modify: `apps/web/src/lib/api.ts`
- Modify: `apps/web/src/lib/api.test.ts`
- Create: `apps/web/src/components/UnifiedEntryComposer.tsx`
- Create: `apps/web/src/components/UnifiedEntryComposer.test.tsx`

- [ ] **Step 1: Write failing adapter tests**

Test the exact response contract and reject unknown intents, extra result keys,
blank model names, fallback modes and non-Gemini providers.

```ts
expect(await routeIntent('Show my last three months')).toEqual({ intent: 'ask_ledger' })
await expect(routeIntent('test')).rejects.toThrow('Intent route response was invalid.')
```

- [ ] **Step 2: Write failing composer tests**

Test loading state, capture callback, assistant callback, clarification buttons,
unsupported copy, provider failure manual choices, repeated-submit suppression,
Enter submission and IME composition safety.

- [ ] **Step 3: Run focused web tests and verify RED**

```bash
npm --prefix apps/web test -- src/lib/api.test.ts src/components/UnifiedEntryComposer.test.tsx
```

Expected: missing exports/component.

- [ ] **Step 4: Implement `routeIntent` strict validation**

```ts
export type UnifiedIntent = 'capture_transaction' | 'ask_ledger' | 'clarify' | 'unsupported'

export async function routeIntent(message: string): Promise<{ intent: UnifiedIntent }> {
  const response = await request<unknown>('/api/v1/intents/route', {
    method: 'POST',
    body: JSON.stringify({ message })
  })
  return parseExactIntentRoute(response)
}
```

Add `/api/v1/intents/route` to retry-safe POST paths because the route is
read-only and idempotent.

- [ ] **Step 5: Implement the focused composer**

The component accepts `variant`, `value`, `onChange`, `onCapture`,
`onAskLedger` and optional `manualAction`. It owns only route status and explicit
recovery choices. Use a generation counter so stale responses cannot invoke a
callback.

- [ ] **Step 6: Run focused tests, lint and types**

```bash
npm --prefix apps/web test -- src/lib/api.test.ts src/components/UnifiedEntryComposer.test.tsx
npm run lint:web
npm run typecheck:web
```

- [ ] **Step 7: Commit the adapter and component**

```bash
git add apps/web/src/types.ts apps/web/src/lib/api.ts apps/web/src/lib/api.test.ts apps/web/src/components/UnifiedEntryComposer.tsx apps/web/src/components/UnifiedEntryComposer.test.tsx
git commit -m "feat: add unified entry composer"
```

### Task 4: Home and Quick Add integration

**Files:**
- Modify: `apps/web/src/pages/HomePage.tsx`
- Modify: `apps/web/src/pages/HomePage.test.tsx`
- Modify: `apps/web/src/pages/QuickAddPage.tsx`
- Modify: `apps/web/src/pages/QuickAddPage.test.tsx`

- [ ] **Step 1: Write failing Home routing tests**

Mock `routeIntent`; assert capture navigates to `/add` with `{capture}`, ledger
question navigates to `/assistant` with a UUID handoff, and copy uses **What
would you like to do?** and **Continue**.

- [ ] **Step 2: Write failing Quick Add routing tests**

Assert an `ask_ledger` result does not call `/drafts/parse`, while a capture
result calls it once. Confirm manual entry bypasses intent routing.

- [ ] **Step 3: Run focused tests and verify RED**

```bash
npm --prefix apps/web test -- src/pages/HomePage.test.tsx src/pages/QuickAddPage.test.tsx
```

- [ ] **Step 4: Integrate the Home composer**

Use `UnifiedEntryComposer` and route ledger questions with:

```ts
navigate('/assistant', {
  initialQuestion: message,
  handoffId: crypto.randomUUID()
})
```

- [ ] **Step 5: Integrate Quick Add without changing confirmation**

Replace only its natural-language submission controls. `onCapture` calls the
existing `makeDraft(message)`; `onAskLedger` navigates to the same assistant
handoff; manual entry continues to call `startManualEntry()`.

- [ ] **Step 6: Run page tests, lint and types**

```bash
npm --prefix apps/web test -- src/pages/HomePage.test.tsx src/pages/QuickAddPage.test.tsx src/components/UnifiedEntryComposer.test.tsx
npm run lint:web
npm run typecheck:web
```

- [ ] **Step 7: Commit entry-point integration**

```bash
git add apps/web/src/pages/HomePage.tsx apps/web/src/pages/HomePage.test.tsx apps/web/src/pages/QuickAddPage.tsx apps/web/src/pages/QuickAddPage.test.tsx
git commit -m "feat: route natural language from home and quick add"
```

### Task 5: One-time Ask Artha handoff

**Files:**
- Modify: `apps/web/src/pages/AssistantPage.tsx`
- Modify: `apps/web/src/pages/AssistantPage.test.tsx`

- [ ] **Step 1: Write failing handoff tests**

Render under `RouterProvider` with history state and assert the initial question
is visible immediately, `chatAssistant` receives it once, history state is
cleared, rerender does not resubmit, refresh state is null and provider failure
restores the exact question for retry.

- [ ] **Step 2: Run the assistant tests and verify RED**

```bash
npm --prefix apps/web test -- src/pages/AssistantPage.test.tsx
```

- [ ] **Step 3: Extract one normal send pipeline**

Implement `sendQuestion(rawQuestion)` and use it from manual submit and the
handoff effect. Add `pendingQuestion` so the user bubble is visible while the
existing **Reviewing your ledger…** status is active.

- [ ] **Step 4: Consume route state once**

Guard with a handled handoff ref and clear browser state before starting the
request:

```ts
window.history.replaceState(null, '', window.location.pathname)
void sendQuestion(initialQuestion)
```

- [ ] **Step 5: Run assistant regression tests**

```bash
npm --prefix apps/web test -- src/pages/AssistantPage.test.tsx
npm run lint:web
npm run typecheck:web
```

- [ ] **Step 6: Commit the handoff**

```bash
git add apps/web/src/pages/AssistantPage.tsx apps/web/src/pages/AssistantPage.test.tsx
git commit -m "feat: continue routed questions in Ask Artha"
```

### Task 6: Router evaluation dataset and release documentation

**Files:**
- Create: `evals/intent-router-cases.jsonl`
- Modify: `apps/api/src/artha_api/feature_evals.py`
- Modify: `apps/api/tests/test_feature_evals.py`
- Modify: `Makefile`
- Modify: `docs/product-requirements.md`
- Modify: `docs/system-architecture.md`
- Modify: `README.md`
- Modify: `docs/PROJECT-CHECKPOINT.md`
- Modify: `docs/SPRINT-BOARD.md`

- [ ] **Step 1: Write failing dataset validation tests**

Require at least 40 unique fictional cases, every intent, at least eight
near-neighbour capture/question pairs, prompt-injection and Indian-English tags.
Reject missing tags, invalid expected intents and duplicates.

- [ ] **Step 2: Add the balanced JSONL dataset**

Each row contains `id`, `message`, `expected_intent` and `tags`. No real user or
ledger data may appear.

- [ ] **Step 3: Add keyless validation and hosted scoring**

Extend `feature_evals --mode validate` to report router case count. Extend
`--mode run --suite all` with exact-intent accuracy, safety accuracy, false
capture count and latency p50/p95. A ledger question incorrectly classified as
capture fails the safety gate.

- [ ] **Step 4: Run evaluator tests and validators**

```bash
cd apps/api && uv run pytest tests/test_feature_evals.py -q
make eval-feature-validate
```

- [ ] **Step 5: Update maintained product and architecture docs**

Document the universal entry as a bounded dispatcher, not an agent. Record the
four intents, direct handoff behavior, no-write boundary, evaluation count and
remaining hosted/live release gates.

- [ ] **Step 6: Run docs checks and commit**

```bash
python3 scripts/check_docs_links.py
git diff --check
git add evals/intent-router-cases.jsonl apps/api/src/artha_api/feature_evals.py apps/api/tests/test_feature_evals.py Makefile README.md docs/product-requirements.md docs/system-architecture.md docs/PROJECT-CHECKPOINT.md docs/SPRINT-BOARD.md
git commit -m "docs: validate and document unified intent routing"
```

### Task 7: Full verification, responsive QA and separate PR

**Files:**
- Modify only if verification finds a scoped defect.

- [ ] **Step 1: Run the full repository gate**

```bash
make check
```

Expected: ESLint, TypeScript, Ruff, mypy, web/API tests, production build, SQL
parsing and all keyless evaluation validators pass.

- [ ] **Step 2: Run a production-style local smoke**

Exercise Home → Quick Add and Home → Ask Artha with mocked hosted responses.
Confirm no transaction exists before explicit confirmation and a ledger question
never invokes draft parsing.

- [ ] **Step 3: Perform responsive and accessibility QA**

Inspect 320, 390 and 1440 CSS px in light/dark mode. Verify no horizontal
overflow, correct focus/live regions, keyboard and IME behavior, visible pending
question, Back behavior and refresh non-duplication.

- [ ] **Step 4: Review the complete branch diff**

```bash
git diff --check origin/main...HEAD
git status --short
git log --oneline origin/main..HEAD
```

Expected: clean worktree and only the unified-intent feature scope.

- [ ] **Step 5: Push and open a separate draft PR**

```bash
git push -u origin codex/unified-entry-router
gh pr create --base main --head codex/unified-entry-router --draft --title "feat: add unified intent entry" --body-file /tmp/artha-unified-entry-pr.md
```

The PR body must include product behavior, trust boundaries, test evidence,
hosted-model/live gates still pending and screenshots for both destination
paths. Do not merge or deploy until CI, hosted fictional routing evaluation and
final-domain smoke tests pass.
