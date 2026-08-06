# Artha product story and AI boundary design

Date: 7 August 2026  
Status: Approved direction; implementation pending

## Objective

Make Artha's public explanation match the product users will experience:

- a private, mobile-first ledger for personal and family money;
- natural-language capture powered by Gemini;
- explicit review before any ledger write;
- trusted database calculations behind assistant answers;
- a clear manual path when AI is unavailable or uncertain.

The README must work for a product or marketing reader while remaining technically
accurate for an engineer. GitHub's About panel must point to the live web app, not
the API service.

## Product positioning

Artha starts with the sentence already in the user's head instead of making the
user complete a form before they can remember an expense. It covers bank
accounts, credit cards, transfers, personal spending and expenses shared with
family or friends in one private ledger.

The central promise is:

> AI helps interpret what happened. You review it. Only confirmation changes the
> ledger.

The README will not compare Artha with, or mention, another expense-sharing
product. The primary examples are:

```text
self transfer 25k ICICI -> HDFC
Paid 1840 for groceries from HDFC, split with Krima, 3 days ago.
```

The copy should explain that Artha proposes amount, transaction type, source and
destination accounts, date, category and sharing details as an unsaved draft.

## Capture architecture

Production natural-language capture uses Gemini as the interpreter. The model is
given only the authenticated household's allowed accounts, members and
categories, and its structured response is validated before it reaches the
review UI.

The production web app will no longer use the browser's deterministic
natural-language parser after an API or model failure. When interpretation is
unavailable or uncertain, Artha will:

1. preserve the original text;
2. explain that automatic interpretation is unavailable;
3. open or offer the manual transaction form;
4. leave all fields editable and save nothing automatically.

The local parser may remain for isolated demo fixtures, evaluation and tests,
but it must not be represented as a production interpretation fallback.

Deterministic code remains authoritative for:

- schema and allow-list validation;
- paise arithmetic and split totals;
- account, member and category grounding;
- authorization and household isolation;
- idempotency and ledger invariants;
- database-derived balances and aggregates.

These are guardrails and sources of truth, not a competing language interpreter.

## Assistant architecture

The assistant remains LLM-powered. Gemini interprets the question, explains the
result and selects from approved inline UI components such as metric cards,
tables and charts.

Financial values are supplied by authenticated, user-scoped database queries.
The model must not calculate or invent balances, totals or shared obligations.
If the model is unavailable, the chat should show an honest unavailable state;
normal dashboard metrics remain accessible through the rest of the product.

## Auto-tagging

Previously confirmed household merchant rules may apply before model inference.
When no rule exists, Gemini may suggest a category from the household's allowed
categories. The user can correct the suggestion, and a confirmed correction may
teach a future merchant rule. This is product learning, not a generic parser
fallback.

## README information architecture

The README will use the following order:

1. concise product promise and production status;
2. a rewritten `Why Artha?` section;
3. natural-language examples and review-before-save principle;
4. product capabilities;
5. a hand-drawn architecture visual;
6. a compact technical stack and links to detailed documents;
7. local setup, testing, deployment and roadmap.

The `Why Artha?` section will avoid implementation jargon until after the user
value is clear. Provider choices and fallbacks belong in the architecture and
configuration sections rather than the opening pitch.

## Architecture visual

Use Option A: two related diagrams presented as one Excalidraw-style SVG asset.

The main trust flow is:

```text
Natural sentence or form
        -> Gemini proposes a grounded, structured draft
        -> user reviews and confirms
        -> ledger updates accounts, cards and shared balances
```

An uncertainty branch leaves Gemini and opens the manual form without saving or
guessing. A smaller deployment strip shows:

```text
React PWA on Vercel -> FastAPI on Vercel -> Supabase Postgres with RLS
                                         -> Gemini through the server only
```

The visual will be stored as a repository SVG so it remains sharp on GitHub. It
must use readable labels, accessible contrast, a descriptive alt attribute and
colors that remain understandable in light and dark GitHub themes. The detailed
technical architecture document remains the source for component-level detail.

## GitHub About metadata

Description:

> Private, mobile-first money tracker for accounts, cards and shared expenses—with natural-language capture and review-before-save AI.

Website:

> https://artha-web-one.vercel.app

Topics:

```text
personal-finance
expense-tracker
money-management
react
fastapi
supabase
pwa
gemini
typescript
```

Model-provider and local-development alternatives stay documented in the repo,
but `qwen`, `ollama` and `open-weight` are removed from the primary About
positioning because they do not describe the current production experience.

## User experience and error states

Capture failure must never look like a successful interpretation. The review
screen must distinguish:

- a validated Gemini draft ready for review;
- a clarification request for missing or ambiguous information;
- an unavailable interpreter with the original text retained;
- manual entry selected by the user.

The assistant must distinguish a valid zero or empty result from provider
unavailability. Error messages must provide a useful next action and remain
responsive at 320 px, 390 px and laptop widths.

## Verification

Implementation is accepted only when:

- production-mode capture does not invoke the local parser after server or model
  failure;
- the original sentence reaches the manual-entry recovery path unchanged;
- successful Gemini capture still grounds accounts, members, categories and
  dates and still requires confirmation;
- assistant replies remain model-powered and all financial values match trusted
  database calculations;
- demo/evaluation parser behavior remains isolated and tested;
- README links, examples, architecture asset and About metadata are correct;
- the architecture SVG is visually checked in GitHub light and dark modes;
- automated web/API tests and focused responsive manual checks pass.

## Out of scope

- Changing the ledger schema or accounting rules.
- Letting the model save transactions directly.
- Model-generated financial arithmetic.
- Adding another hosted model provider as an automatic production fallback.
- Rebranding the product beyond the approved Artha name.
