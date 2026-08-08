# AI-Primary Capture and Product Story Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make Gemini the only production natural-language interpreter and assistant response generator, recover capture failures through an honest manual form, and align the README, architecture visual, technical docs, and GitHub About metadata with that behavior.

**Architecture:** Production Quick Add calls the authenticated FastAPI capture endpoint and accepts only its grounded, validated Gemini draft. A provider or transport failure becomes a typed client error that opens a blank manual draft while retaining the original sentence; the local parser remains isolated to demo and evaluation mode. Assistant and tag endpoints fail with HTTP 503 when no configured LLM returns valid output, while all balances and aggregates continue to come from authenticated database calculations.

**Tech Stack:** React 19, TypeScript, Vite, Tailwind CSS, Vitest, Python 3.13, FastAPI, Pydantic v2, pytest, Gemini, SVG, GitHub CLI.

---

## File map

| File | Responsibility |
| --- | --- |
| `apps/web/src/lib/api.ts` | Production capture/assistant transport behavior and typed unavailable error |
| `apps/web/src/lib/api.test.ts` | Adapter-level proof that production never invokes local interpretation |
| `apps/web/src/pages/QuickAddPage.tsx` | Preserve text and open manual entry after automatic interpretation fails |
| `apps/web/src/pages/QuickAddPage.test.tsx` | User-visible capture recovery behavior |
| `apps/web/src/pages/AssistantPage.tsx` | Show only genuine model replies or an honest unavailable state |
| `apps/web/src/pages/AssistantPage.test.tsx` | Assistant provider failure and response-label behavior |
| `apps/web/src/types.ts` | Remove the deterministic-assistant response flag from the web contract |
| `apps/api/src/artha_api/assistant.py` | Raise a typed unavailable error when every LLM attempt fails |
| `apps/api/src/artha_api/assistant_routes.py` | Convert unavailable assistant/tag inference into HTTP 503 in local mode |
| `apps/api/src/artha_api/production_routes.py` | Convert unavailable assistant/tag inference into HTTP 503 in production |
| `apps/api/tests/test_assistant.py` | Model-only assistant/tag unit and endpoint contracts |
| `docs/assets/artha-architecture.svg` | Hand-drawn, repository-owned trust/deployment diagram |
| `README.md` | Product positioning, examples, architecture and current Gemini behavior |
| `docs/system-architecture.md` | Detailed current runtime and failure boundaries |
| `docs/artifacts/architecture/v1-llm-usage-map.md` | Current Gemini capture/tag/assistant usage map |
| `docs/PROJECT-CHECKPOINT.md` | Dated implementation and verification evidence |
| `docs/SPRINT-BOARD.md` | Completed task state and remaining acceptance work |

### Task 1: Make production capture fail into manual entry

**Files:**
- Modify: `apps/web/src/lib/api.test.ts`
- Modify: `apps/web/src/lib/api.ts`
- Modify: `apps/web/src/pages/QuickAddPage.test.tsx`
- Modify: `apps/web/src/pages/QuickAddPage.tsx`

- [ ] **Step 1: Write the adapter test that forbids production local parsing**

Add a production-mode test whose parse endpoint returns 503 while the account and
member endpoints remain available:

```ts
it('never interprets production capture locally after an AI or API failure', async () => {
  vi.stubEnv('VITE_API_URL', 'https://api.artha.test')
  vi.stubEnv('VITE_DEMO_MODE', 'false')
  vi.stubGlobal('fetch', vi.fn(async (input: RequestInfo | URL) => {
    const url = String(input)
    if (url.endsWith('/api/v1/drafts/parse')) return new Response('{}', { status: 503 })
    if (url.endsWith('/api/v1/accounts')) return Response.json([{ id: 42, name: 'HDFC UPI' }])
    if (url.endsWith('/api/v1/members')) return Response.json([])
    return new Response('{}', { status: 404 })
  }))
  const { CaptureDraftUnavailableError, parseDraft } = await import('./api')

  await expect(parseDraft('self transfer 25k ICICI -> HDFC')).rejects.toEqual(
    expect.objectContaining({
      name: 'CaptureDraftUnavailableError',
      sourceText: 'self transfer 25k ICICI -> HDFC'
    })
  )
  expect(CaptureDraftUnavailableError).toBeTypeOf('function')
})
```

- [ ] **Step 2: Run the adapter test and verify RED**

Run:

```bash
npm --prefix apps/web test -- src/lib/api.test.ts -t "never interprets production capture locally"
```

Expected: FAIL because `CaptureDraftUnavailableError` does not exist and the
current adapter attempts `parseCaptureLocally` in production.

- [ ] **Step 3: Add the typed unavailable error and restrict local parsing to demo mode**

Add near the other API error types in `apps/web/src/lib/api.ts`:

```ts
export class CaptureDraftUnavailableError extends Error {
  readonly sourceText: string

  constructor(sourceText: string, options?: ErrorOptions) {
    super('Automatic interpretation is temporarily unavailable.', options)
    this.name = 'CaptureDraftUnavailableError'
    this.sourceText = sourceText
  }
}
```

Replace the `parseDraft` catch block with:

```ts
  } catch (error) {
    if (error instanceof ApiError && error.status >= 400 && error.status < 500) throw error
    if (DEMO_MODE) {
      return { data: parseCaptureLocally(text, membersForFallback), demo: true }
    }
    throw new CaptureDraftUnavailableError(text, { cause: error })
  }
```

Do not fetch accounts or call `parseCaptureLocally` inside the production branch.

- [ ] **Step 4: Run the adapter tests and verify GREEN**

Run:

```bash
npm --prefix apps/web test -- src/lib/api.test.ts
```

Expected: all adapter tests PASS, including the existing demo-only local-parser
test.

- [ ] **Step 5: Write the Quick Add recovery test**

In `QuickAddPage.test.tsx`, mock the API module with its real exports overridden
for the focused test, then assert that the input survives and the manual form is
opened without confirmation:

```ts
it('preserves the sentence and opens manual entry when AI capture is unavailable', async () => {
  const user = userEvent.setup()
  const onConfirm = vi.fn()
  const sourceText = 'self transfer 25k ICICI -> HDFC'
  vi.spyOn(api, 'parseDraft').mockRejectedValueOnce(
    new api.CaptureDraftUnavailableError(sourceText)
  )
  render(<RouterProvider><QuickAddPage onConfirm={onConfirm} members={[]} /></RouterProvider>)

  await user.type(screen.getByLabelText(/your message/i), sourceText)
  await user.click(screen.getByRole('button', { name: /create review draft/i }))

  expect(await screen.findByRole('alert')).toHaveTextContent(
    /automatic interpretation is temporarily unavailable/i
  )
  expect(screen.getByLabelText(/your message/i)).toHaveValue(sourceText)
  expect(screen.getByLabelText('Amount in rupees')).toHaveValue(null)
  expect(screen.getByText(/nothing has been saved yet/i)).toBeInTheDocument()
  expect(onConfirm).not.toHaveBeenCalled()
})
```

Import the API namespace with `import * as api from '../lib/api'`. Restore the
spy in `afterEach` with `vi.restoreAllMocks()`.

- [ ] **Step 6: Run the Quick Add test and verify RED**

Run:

```bash
npm --prefix apps/web test -- src/pages/QuickAddPage.test.tsx -t "preserves the sentence"
```

Expected: FAIL because Quick Add currently displays only an error and does not
create a manual draft.

- [ ] **Step 7: Open a manual draft only for the typed unavailable error**

Import `CaptureDraftUnavailableError`. Update the failure branch:

```ts
    } catch (caught) {
      if (caught instanceof CaptureDraftUnavailableError) {
        startManualEntry(caught.sourceText)
        setError(`${caught.message} Your text is still here; enter the remaining details below. Nothing was saved.`)
      } else {
        setError(userFacingFailure(caught, 'We could not read that. Check the details and try again.'))
      }
    }
```

Allow the manual helper to retain the sentence in the unsaved draft:

```ts
  function startManualEntry(sourceText = '') {
    const firstAccount = accounts[0]
    setDraft({
      kind: 'debit', amountPaise: 0, merchant: '', category: 'Other',
      account: firstAccount?.name ?? 'Primary account', sourceAccountId: firstAccount?.id,
      occurredAt: localDateOffset(0), note: '', memberSplits: [], confidence: 'review', sourceText
    })
    setUsedFallback(false)
    setError('')
  }
```

Because `startManualEntry` clears errors, set the recovery message after calling
it. Existing manual-entry button calls must use `onClick={() => startManualEntry()}`
so React does not pass the click event as `sourceText`.

- [ ] **Step 8: Run focused and full web tests**

Run:

```bash
npm --prefix apps/web test -- src/pages/QuickAddPage.test.tsx src/lib/api.test.ts
npm run typecheck:web
```

Expected: focused tests and TypeScript checks PASS.

- [ ] **Step 9: Commit capture recovery**

```bash
git add apps/web/src/lib/api.ts apps/web/src/lib/api.test.ts apps/web/src/pages/QuickAddPage.tsx apps/web/src/pages/QuickAddPage.test.tsx
git commit -m "fix: fail AI capture into manual review"
```

### Task 2: Make assistant and model tagging fail honestly

**Files:**
- Modify: `apps/api/tests/test_assistant.py`
- Modify: `apps/api/src/artha_api/assistant.py`
- Modify: `apps/api/src/artha_api/assistant_routes.py`
- Modify: `apps/api/src/artha_api/production_routes.py`

- [ ] **Step 1: Replace fallback expectations with model-unavailable expectations**

Add or rewrite unit tests in `test_assistant.py`:

```python
@pytest.mark.asyncio
async def test_disabled_assistant_fails_closed(
    financial_context: AssistantFinancialContext,
) -> None:
    assistant = LocalFinancialAssistant(AssistantSettings(provider=LlmProvider.DISABLED))

    with pytest.raises(AssistantUnavailableError, match="assistant is unavailable"):
        await assistant.chat("How much did I spend?", financial_context)


@pytest.mark.asyncio
async def test_invalid_model_payload_does_not_become_a_generated_financial_answer(
    financial_context: AssistantFinancialContext,
) -> None:
    assistant = LocalFinancialAssistant(
        AssistantSettings(provider=LlmProvider.OLLAMA),
        transport=httpx.MockTransport(lambda _: httpx.Response(200, json={"message": {"content": "{}"}})),
    )

    with pytest.raises(AssistantUnavailableError):
        await assistant.chat("What is my balance?", financial_context)
```

Update the disabled-provider endpoint test so `/assistant/chat` and
`/assistant/tag-suggestion` return 503 and the transaction list remains
unchanged.

- [ ] **Step 2: Run the assistant tests and verify RED**

Run:

```bash
cd apps/api && uv run pytest tests/test_assistant.py -k "fails_closed or does_not_become or endpoints_are_read_only" -q
```

Expected: FAIL because the assistant currently returns deterministic generated
responses with HTTP 200.

- [ ] **Step 3: Introduce the unavailable exception and remove generated fallbacks**

Add to `assistant.py`:

```python
class AssistantUnavailableError(RuntimeError):
    """No configured model produced a valid, grounded response."""
```

After all model attempts fail in `chat`, replace the deterministic response with:

```python
raise AssistantUnavailableError("AI assistant is unavailable")
```

After all model attempts fail in `suggest_tag`, replace the deterministic tag
response with:

```python
raise AssistantUnavailableError("AI category suggestion is unavailable")
```

Narrow `AssistantChatResponse.mode` and `TagSuggestionResponse.mode` to
`Literal["model"]`. Keep database-derived context creation unchanged.

- [ ] **Step 4: Map unavailable inference to HTTP 503 in both route modules**

Wrap assistant and tag calls in `assistant_routes.py` and
`production_routes.py`:

```python
try:
    return await assistant.chat(payload.message, context)
except AssistantUnavailableError as error:
    raise HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail="The AI assistant is temporarily unavailable. Your ledger was not changed.",
    ) from error
```

Use the corresponding category-suggestion message for tag routes. Import
`AssistantUnavailableError`, `HTTPException`, and `status` where required.

- [ ] **Step 5: Run focused assistant tests and verify GREEN**

Run:

```bash
cd apps/api && uv run pytest tests/test_assistant.py tests/test_production_routes.py -q
```

Expected: all focused API tests PASS.

- [ ] **Step 6: Run API type and lint checks**

Run:

```bash
cd apps/api && uv run ruff check . && uv run mypy
```

Expected: both checks PASS with no warnings.

- [ ] **Step 7: Commit model-only API behavior**

```bash
git add apps/api/src/artha_api/assistant.py apps/api/src/artha_api/assistant_routes.py apps/api/src/artha_api/production_routes.py apps/api/tests/test_assistant.py apps/api/tests/test_production_routes.py
git commit -m "fix: keep assistant responses model powered"
```

### Task 3: Remove deterministic-assistant presentation from the web app

**Files:**
- Modify: `apps/web/src/types.ts`
- Modify: `apps/web/src/lib/api.test.ts`
- Modify: `apps/web/src/lib/api.ts`
- Modify: `apps/web/src/pages/AssistantPage.test.tsx`
- Modify: `apps/web/src/pages/AssistantPage.tsx`

- [ ] **Step 1: Write tests for genuine provider replies and unavailable UI**

Update reply fixtures to omit `deterministicFallback`. Add:

```ts
it('labels a successful reply as AI powered', async () => {
  vi.mocked(chatAssistant).mockResolvedValue({
    message: 'Your available balance is shown below.',
    provider: 'gemini · gemini-3.5-flash-lite',
    widgets: [{ type: 'metric', title: 'Available balance', value: '₹25,000' }]
  })
  const user = userEvent.setup()
  render(<AssistantPage />)

  await user.type(screen.getByLabelText('Ask Artha'), 'What is my balance?')
  await user.click(screen.getByRole('button', { name: 'Send question' }))

  expect(await screen.findByText('AI response')).toBeInTheDocument()
  expect(screen.queryByText(/deterministic fallback/i)).not.toBeInTheDocument()
})
```

The existing error-path assertion must verify that the question is restored and
the alert says the ledger was not changed.

- [ ] **Step 2: Run the Assistant page tests and verify RED**

Run:

```bash
npm --prefix apps/web test -- src/pages/AssistantPage.test.tsx
```

Expected: FAIL because the reply contract and badge still expose deterministic
fallback behavior.

- [ ] **Step 3: Narrow the web reply contract and remove demo-generated answers**

Change `AssistantReply` to:

```ts
export interface AssistantReply {
  message: string
  widgets: AssistantWidget[]
  provider: string
}
```

In `chatAssistant`, return only parsed provider responses. Remove the demo catch
that fabricates deterministic metric and insight widgets; propagate the request
error so the page shows its existing unavailable state.

- [ ] **Step 4: Replace the fallback badge with a truthful AI badge**

In `ExchangeView`, render:

```tsx
<Badge tone="green">AI response</Badge>
<span className="text-[11px] font-semibold text-[#76837c] tone-muted">
  {exchange.reply.provider}
</span>
```

Keep the statement that only approved widgets render and financial decisions
should be verified against transactions.

- [ ] **Step 5: Run web tests, types and lint**

Run:

```bash
npm --prefix apps/web test -- src/pages/AssistantPage.test.tsx src/lib/api.test.ts
npm run typecheck:web
npm run lint:web
```

Expected: all commands PASS.

- [ ] **Step 6: Commit assistant UI contract**

```bash
git add apps/web/src/types.ts apps/web/src/lib/api.ts apps/web/src/lib/api.test.ts apps/web/src/pages/AssistantPage.tsx apps/web/src/pages/AssistantPage.test.tsx
git commit -m "fix: show only AI-powered assistant replies"
```

### Task 4: Replace the README story and architecture

**Files:**
- Create: `docs/assets/artha-architecture.svg`
- Modify: `README.md`
- Modify: `docs/system-architecture.md`
- Modify: `docs/artifacts/architecture/v1-llm-usage-map.md`

- [ ] **Step 1: Create the hand-drawn SVG architecture asset**

Create an accessible SVG with `viewBox="0 0 1200 620"`, rounded hand-drawn
boxes, slightly offset duplicate strokes, arrow markers, and this exact semantic
flow:

```text
Say or type -> Gemini interprets -> Review and confirm -> Ledger truth
                     |
                     +-> unavailable or unsure -> keep text and open the form

React PWA / Vercel -> FastAPI / Vercel -> Supabase Postgres / RLS
                                          -> Gemini / server only
```

Include `<title>Artha review-before-save architecture</title>` and
`<desc>Gemini proposes a grounded draft, the user reviews it, and only explicit confirmation updates the private ledger.</desc>`.
Use CSS variables plus `@media (prefers-color-scheme: dark)` so text, fills, and
strokes retain contrast in GitHub light and dark themes.

- [ ] **Step 2: Render and visually inspect the SVG**

Run:

```bash
rsvg-convert docs/assets/artha-architecture.svg -o /tmp/artha-architecture.png
```

Expected: a 1200-by-620 readable PNG with no clipped labels or overlapping
arrows. If `rsvg-convert` is unavailable, open the SVG directly in the browser
and capture it at its native viewBox.

- [ ] **Step 3: Rewrite `Why Artha?` around user value**

Use this approved copy as the base:

```markdown
## Why Artha?

Money tracking often fails at the exact moment it asks you to stop and do
bookkeeping. Artha starts with the sentence already in your head:

> `Paid ₹1,840 for groceries from HDFC, split with Krima, three days ago.`

Or simply:

> `self transfer 25k ICICI -> HDFC`

Artha turns that into an **unsaved draft** containing the amount, transaction
type, accounts, date, category and sharing details. Review it, correct anything,
then confirm. Only confirmation changes the ledger.

That gives you one private view across bank accounts, cards, internal transfers,
personal spending and expenses shared with family or friends—without making the
capture itself feel like accounting.

> **AI interprets. Artha validates. You decide what gets saved.**
```

Do not mention any competing product.

- [ ] **Step 4: Replace the Mermaid diagram and stale AI table row**

Embed:

```markdown
![Artha review-before-save architecture](docs/assets/artha-architecture.svg)
```

Describe Gemini as the production interpreter and read-only assistant. Describe
the manual form as the failure path. Do not describe Qwen, Ollama, Groq or a
deterministic parser as the current production experience; keep local model
configuration only in a clearly marked development/provider-portability note.

- [ ] **Step 5: Update the detailed architecture and LLM usage map**

In both technical documents, make these facts explicit:

1. Gemini receives server-grounded household context and returns validated JSON.
2. Capture output is always an unsaved draft.
3. Provider failure preserves input and routes to manual entry.
4. Assistant totals are database-derived and the LLM explains/renders them.
5. Merchant rules are learned product behavior, not a language-parser fallback.
6. Local parsers and alternative providers are demo/evaluation or portability tools.

Replace the old Qwen-first status and deterministic-fallback flow diagrams.

- [ ] **Step 6: Run documentation checks**

Run:

```bash
rg -n "Splitwise|Mira|deterministic (capture )?parser|deterministic fallback|Hosted Qwen enabled|open-weight family selected" README.md docs/system-architecture.md docs/artifacts/architecture/v1-llm-usage-map.md
python - <<'PY'
from pathlib import Path
for path in [Path('README.md'), Path('docs/system-architecture.md'), Path('docs/artifacts/architecture/v1-llm-usage-map.md')]:
    text = path.read_text()
    assert 'Gemini' in text, path
    assert 'review' in text.lower(), path
assert Path('docs/assets/artha-architecture.svg').is_file()
print('documentation contracts passed')
PY
```

Expected: the `rg` command returns no stale product-story matches; the Python
contract prints `documentation contracts passed`.

- [ ] **Step 7: Commit product documentation**

```bash
git add README.md docs/assets/artha-architecture.svg docs/system-architecture.md docs/artifacts/architecture/v1-llm-usage-map.md
git commit -m "docs: clarify Artha product and AI architecture"
```

### Task 5: Run release gates and record evidence

**Files:**
- Modify: `docs/PROJECT-CHECKPOINT.md`
- Modify: `docs/SPRINT-BOARD.md`

- [ ] **Step 1: Run the complete repository gate**

Run:

```bash
make check
```

Expected: web lint, TypeScript, Vitest, Vite production build, Ruff, mypy,
pytest, SQL checks, and all keyless evaluation contracts PASS.

- [ ] **Step 2: Run the hosted fictional Gemini gates**

Run only with the existing ignored server-side key:

```bash
make eval-capture-hosted
make eval-feature-hosted
```

Expected: capture, auto-tagging and assistant fictional suites meet their
checked-in acceptance thresholds without sending real finance text.

- [ ] **Step 3: Manually verify responsive recovery and assistant states**

Start the app with production-like environment values and inspect 320 px, 390 px,
and 1440 px widths:

1. Gemini capture success creates a grounded unsaved draft.
2. A forced 503 keeps the sentence and opens the manual form.
3. Confirmation remains disabled for zero amount and incomplete transfers.
4. Assistant success renders the `AI response` badge and approved widgets.
5. Assistant 503 restores the question and shows the honest error state.
6. Light and dark themes have no clipped cards, horizontal page overflow, or
   unreadable architecture artwork.

- [ ] **Step 4: Record exact verification evidence**

Append a dated row to `PROJECT-CHECKPOINT.md` containing actual test counts and
manual viewport results. Mark the corresponding capture/assistant/product-story
items complete in `SPRINT-BOARD.md`; do not mark two-owner isolation or final
restore acceptance complete unless separately proven.

- [ ] **Step 5: Commit release evidence**

```bash
git add docs/PROJECT-CHECKPOINT.md docs/SPRINT-BOARD.md
git commit -m "docs: record AI-primary release evidence"
```

### Task 6: Update GitHub About and publish

**Files:**
- No repository file changes; GitHub repository metadata and branch publication

- [ ] **Step 1: Verify authentication and target repository**

Run:

```bash
gh auth status
gh repo view snayan06/artha --json nameWithOwner,description,homepageUrl,repositoryTopics
```

Expected: authenticated as the intended GitHub account and target resolves to
`snayan06/artha`.

- [ ] **Step 2: Update description and live-app homepage**

Run:

```bash
gh repo edit snayan06/artha \
  --description "Private, mobile-first money tracker for accounts, cards and shared expenses—with natural-language capture and review-before-save AI." \
  --homepage "https://artha-web-one.vercel.app"
```

- [ ] **Step 3: Replace stale positioning topics**

Remove the stale provider-specific `ollama` and `qwen` topics, retain the
accurate `open-source` topic, then add the approved product/stack topics:

```bash
gh repo edit snayan06/artha --remove-topic ollama --remove-topic qwen
gh repo edit snayan06/artha --add-topic open-source --add-topic personal-finance --add-topic expense-tracker --add-topic money-management --add-topic react --add-topic fastapi --add-topic supabase --add-topic pwa --add-topic gemini --add-topic typescript
```

If a removed topic is already absent, continue and verify the final set rather
than treating absence as a release failure.

- [ ] **Step 4: Verify metadata exactly**

Run:

```bash
gh repo view snayan06/artha --json description,homepageUrl,repositoryTopics
```

Expected: the approved description, `https://artha-web-one.vercel.app`, and the
ten approved topics are present; the API URL is not the homepage.

- [ ] **Step 5: Push the tested branch and open the normal review path**

Use the repository's publishing workflow to push `codex/current-production` and
open a pull request against `main`. Do not force-push or merge before checks are
green.

- [ ] **Step 6: Verify deployed behavior after merge**

After the normal merge and Vercel deployment complete, repeat the five manual
production checks from Task 5 using fictional data and verify the live README
renders the SVG on GitHub.
