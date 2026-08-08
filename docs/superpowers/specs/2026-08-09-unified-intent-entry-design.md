# Unified intent entry — product requirements and design

Status: approved for implementation
Date: 9 August 2026
Owner: Artha product and engineering

## 1. Summary

Artha's primary natural-language input will accept both money events and ledger
questions. A small, server-side Gemini router classifies the message and sends
the user directly into the correct existing workflow:

- a money event opens Quick Add and creates an **unsaved review draft**;
- a ledger question opens Ask Artha with the exact question already submitted;
- an ambiguous request preserves the text and asks the user to choose between
  the two supported paths;
- an unsupported request remains unsaved and receives a clear scope message.

The router is not an agent. It selects one of a fixed set of application-owned
workflows and has no database, calculation or write authority.

## 2. Problem

The Home card currently asks **What happened?** and its only action is **Make
draft**. That wording teaches users that the input accepts transactions only.
Ask Artha lives in a separate navigation destination, so a user who naturally
types “Show my spending analysis for the last three months” into the prominent
Home input is sent to the wrong workflow.

People should express their intent before they understand Artha's navigation.
The product, not the person, should choose the correct supported workflow.

## 3. Goals

1. Let a user add a transaction or ask a ledger question from the Home input.
2. Apply the same routing behavior to the natural-language composer on the full
   Quick Add page.
3. Move to the destination immediately after classification; never show a
   dedicated routing screen.
4. Preserve the exact message across navigation, failures and manual choices.
5. Keep a single Ask Artha conversation surface and a single Quick Add review
   surface.
6. Preserve every existing ledger safety rule: routing and parsing never write;
   only explicit confirmation can create a transaction.
7. Keep model routing strict, bounded, observable and independently testable.

## 4. Non-goals

- Multi-step autonomous agents, tool planning or background actions.
- Creating, editing or deleting ledger records from Ask Artha.
- Investment advice, external web research or arbitrary database questions.
- Combining the Assistant and Quick Add pages into one large chat interface.
- Persisting incomplete user messages as financial records.
- Exposing model reasoning or chain-of-thought.

## 5. Supported intents

| Router intent | Meaning | Product outcome |
|---|---|---|
| `capture_transaction` | The message describes an expense, income, transfer, card payment or other supported money event | Navigate to Quick Add and run existing draft interpretation |
| `ask_ledger` | The message requests a balance, summary, comparison, trend, category analysis, shared balance or recent activity | Navigate to Ask Artha and submit the question automatically |
| `clarify` | The message could reasonably be either a money event or a ledger question | Preserve the text and show two explicit destination choices |
| `unsupported` | The request is outside both supported workflows | Preserve the text and explain the current scope without calling either downstream workflow |

The classifier must prefer `clarify` over guessing. Its response contains no
amount, category, account, answer, database ID or financial calculation.

## 6. User experience

### 6.1 Home composer

Replace transaction-only copy with:

- Heading: **What would you like to do?**
- Supporting text: **Add a transaction or ask Artha about your money.**
- Placeholder: **Paid ₹850 at Zomato from HDFC, or show my last 3 months**
- Primary action: **Continue**
- Safety note: **Transactions are never saved until you review and confirm.**

Pressing Enter submits on a single-line Home input. The button and input are
disabled only while routing. A compact inline status reads **Understanding your
request…**; it must not create a separate interstitial page.

### 6.2 Direct assistant handoff

For `ask_ledger`:

1. Home or Quick Add navigates directly to `/assistant`.
2. The exact normalized question appears immediately as the user's message.
3. Ask Artha starts the existing chat request automatically and shows its
   existing **Reviewing your ledger…** status.
4. The response renders in the normal assistant history using existing safe
   cards, charts, tables or clarification widgets.
5. The initial question is consumed once. Rerendering cannot submit it twice.
6. If the assistant fails, the question remains in the composer for retry and
   the ledger remains unchanged.

There is no “Taking you to Ask Artha” screen and no duplicate compact answer on
Home. Browser Back returns to the source page with the original composer clear
only after a successful route decision.

### 6.3 Direct capture handoff

For `capture_transaction`:

1. Home navigates directly to `/add` with the exact message.
2. The full Quick Add page runs the existing capture interpreter once and shows
   its unsaved review state.
3. The user reviews and edits the result.
4. Only the existing explicit confirmation action may write to the ledger.

When the user starts inside Quick Add, the page stays in place and runs capture
interpretation directly after routing.

### 6.4 Ambiguous request

For `clarify`, show an inline card beneath the source composer:

> **What would you like Artha to do with this?**

- **Add a transaction**
- **Ask about my ledger**

Choosing a destination bypasses routing and invokes that workflow with the
original message. The card never edits the message or saves data. Manual entry
remains available on Quick Add.

### 6.5 Unsupported request

Show:

> **Artha can currently add transactions or answer questions about your
> ledger. Try rephrasing your request.**

The message remains editable. No downstream model call or write occurs.

### 6.6 Examples

| Message | Expected route |
|---|---|
| `Paid 850 at Zomato from HDFC yesterday` | `capture_transaction` |
| `Self transfer 25k ICICI to HDFC` | `capture_transaction` |
| `Received 45,000 salary in ICICI` | `capture_transaction` |
| `Show my spending analysis for the last 3 months` | `ask_ledger` |
| `How much does Harmi owe me?` | `ask_ledger` |
| `Where did most of my money go in July?` | `ask_ledger` |
| `Zomato` | `clarify` |
| `Help me buy a stock` | `unsupported` |

## 7. Technical design

### 7.1 API contract

Add authenticated endpoint:

`POST /api/v1/intents/route`

Request:

```json
{
  "message": "Show my spending analysis for the last 3 months"
}
```

Response:

```json
{
  "provider": "gemini",
  "model": "gemini-3.5-flash-lite",
  "mode": "model",
  "result": {
    "intent": "ask_ledger"
  }
}
```

The request is whitespace-normalized, non-empty and at most 500 characters.
The response uses a strict Pydantic schema with `extra="forbid"`. No free-form
model explanation is returned to the browser or stored.

### 7.2 Router model boundary

`LocalFinancialAssistant.route_intent(message)` uses the configured Gemini
provider with:

- a fixed four-value enum;
- JSON structured output;
- temperature-equivalent deterministic settings and minimal thinking;
- `store=false`;
- no household context, database snapshot, tools or credentials;
- the same provider timeout and sanitized failure handling as other AI paths.

The router system instruction defines examples and explicitly distinguishes a
statement of a money event from a question about historical ledger data. The
message is untrusted data, not an instruction.

### 7.3 Web adapter

Add `routeIntent(message)` to the strict API adapter. It validates exact keys,
the model response mode, supported provider and the four allowed intent values.
Malformed payloads are failures, not guessed routes.

### 7.4 Destination handoff

Use router history state for a one-time, in-session handoff:

```ts
type AssistantRouteState = {
  initialQuestion: string
  handoffId: string
}
```

Ask Artha consumes `initialQuestion` exactly once per `handoffId`. The page puts
the question into its normal send pipeline; it does not maintain a second chat
implementation. The state is cleared with `history.replaceState` after it is
accepted, preventing refresh or rerender duplication.

Quick Add continues using its existing `capture` route state. A routed message
inside Quick Add bypasses a second router call and enters `makeDraft` directly.

### 7.5 Component boundaries

- `UnifiedMoneyComposer`: owns input, loading, router failure and explicit
  clarification choices; it never parses or answers messages.
- `routeIntent`: owns the strict HTTP adapter contract.
- `IntentRouter` backend models/service: owns only bounded classification.
- `AssistantPage`: owns one-time question consumption and existing conversation.
- `QuickAddPage`: owns capture interpretation, review and confirmation.

## 8. Failure and recovery behavior

| Failure | User experience | Safety result |
|---|---|---|
| Router timeout/network/503 | Keep message; show **Artha could not understand where to send this. Choose an option below.** with the two destination choices | No route guessed, no write |
| Invalid router JSON | Same explicit two-choice recovery | No model output trusted |
| Assistant failure after handoff | Question remains retryable in Ask Artha | No ledger change |
| Capture failure after handoff | Existing exact-text manual recovery | No ledger change |
| Double click / repeated Enter | One in-flight router request; later submissions ignored | No duplicate downstream call |
| Back during routing | Abort or ignore stale response using a request generation ID | No late navigation |
| Refresh on Assistant | Consumed handoff is not automatically submitted again | No duplicate model call |

The two manual route choices are recovery controls, not a deterministic parser.

## 9. Accessibility and responsive behavior

- Router status uses `role="status"` and polite live announcement.
- Failure and unsupported states use an accessible alert.
- Destination choice buttons are keyboard reachable, at least 44 px high and
  have explicit labels.
- Focus moves to the Quick Add review heading or the Ask Artha conversation
  status after the destination is selected.
- Enter submits; Shift+Enter inserts a newline on the multiline Quick Add
  composer; IME composition Enter never submits.
- No horizontal overflow at 320, 390 or 1440 CSS px in light or dark mode.
- Reduced-motion users receive no animated route transition.

## 10. Privacy and security

- The endpoint requires the existing authenticated request boundary.
- The browser never receives a Gemini key.
- The router sends only the user's submitted message, not account balances,
  member lists or transaction history.
- The router cannot call Supabase, invoke ledger RPCs or return database IDs.
- Existing AI data-use policy applies before enabling routing for personal data.
- Logs and analytics record only outcome, latency bucket and failure class;
  never raw message text or financial values.
- Model reasoning is neither requested nor exposed.

## 11. Product analytics

Privacy-safe events:

- `unified_entry_submitted` with source `home|quick_add`;
- `unified_entry_routed` with destination `capture|assistant|clarify|unsupported`;
- `unified_entry_manual_choice` with selected destination;
- `unified_entry_failed` with sanitized failure class;
- `assistant_handoff_completed` and `capture_handoff_completed`.

No event may include the message, amount, merchant, account, category, member or
assistant answer. Analytics are not required for the first release if the
current privacy-filtered telemetry adapter cannot express these events safely.

## 12. Evaluation and testing

### Router dataset

Add a balanced fictional evaluation set covering:

- expenses, income, transfers and card payments;
- analytical questions across summary, spending, income, cash flow, shared and
  recent-transaction intents;
- short ambiguous fragments;
- unsupported advice, write requests and prompt injection;
- Indian English, INR shorthand, merchant names and relative dates;
- near-neighbour pairs such as `Paid 850 for food` versus `How much did I pay
  for food?`.

The keyless validator checks schema and coverage. A hosted fictional gate must
meet 100% schema validity and the agreed classification threshold before
deployment; false routing from `ask_ledger` to `capture_transaction` is treated
as the highest-severity classification error.

### Automated tests

- API schema rejects blanks, overlength messages, extra fields and invalid
  model intents.
- Model failures return sanitized 503s.
- Home routes capture and assistant messages correctly.
- Quick Add routes a ledger question without starting draft parsing.
- Assistant consumes a handoff exactly once and preserves retry text on error.
- Clarification and router failure choices reuse exact source text.
- Double submission and stale responses do not navigate twice.
- Existing review-before-save and read-only assistant tests stay green.

### Manual acceptance

At 390 px mobile and 1440 px desktop, in light and dark mode:

1. Submit a transaction from Home; verify a draft appears and nothing is saved.
2. Submit a three-month analysis question from Home; verify Ask Artha opens
   immediately with the question visible and its answer loading.
3. Submit a ledger question from Quick Add; verify no draft parser runs.
4. Force router unavailability; verify exact text and both manual choices.
5. Refresh during/after assistant handoff; verify no duplicate question.
6. Use Back and resubmit; verify predictable history and focus.

## 13. Rollout and release gate

1. Ship endpoint, adapter and dataset behind no new client-visible capability.
2. Enable the unified Home composer and Quick Add routing together so behavior
   is consistent.
3. Run the complete repository gate plus hosted fictional router evaluation.
4. Deploy API before web.
5. Smoke-test both destination paths on the final production URL.
6. Monitor only privacy-safe route/failure counts; retain the explicit manual
   choice recovery if provider availability degrades.

## 14. Acceptance criteria

- A user can type either supported job into Home without selecting a tab first.
- `ask_ledger` moves directly to Ask Artha; no routing interstitial is shown.
- The exact question is submitted once and becomes part of the existing chat.
- `capture_transaction` reaches the existing unsaved review flow.
- Ambiguous or failed routing never guesses and always preserves the message.
- No router path can write, calculate ledger truth or expose provider reasoning.
- All automated, responsive, accessibility, hosted-model and live smoke gates
  pass before merge or deployment.
