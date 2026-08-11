# Artha Analyst — bounded agent and evaluation plan

Status: planned behind a demo/test-account flag

Date: 11 August 2026

## Product thesis

Ask Artha should become a **bounded, read-only financial analyst**, not a chat
bot with direct ledger authority. It should answer questions, compare periods,
explain drivers and run user-controlled cash scenarios. Every number comes from
server-owned tools or deterministic calculators. The model chooses tools and
presentation; it never writes SQL, calculates ledger truth or mutates money.

The interview-ready engineering story is:

> A privacy-aware financial agent built with typed function calls, deterministic
> tools, evidence-linked generative UI, explicit authority boundaries and an
> end-to-end evaluation harness.

## Current product diagnosis

The current assistant is safe but narrow:

- Gemini selects one of eight fixed intents.
- The server supplies one prebuilt widget bundle for that intent.
- Only this month's totals, five categories, six monthly points and eight recent
  movements reach the model.
- Conversation history remains in the browser and is not resolved by the API.
- Answers do not expose their date range, source count or matching transactions.

This explains why the assistant can show a balance or trend but cannot yet
answer “why?”, “compared with what?”, “what if?” or a contextual follow-up.

## Current external facts

The design is based on current primary documentation, not framework fashion:

- Google's Interactions API is the recommended API for new Gemini agentic work.
  It exposes observable execution steps and supports stateless `store=false`
  requests.
- Gemini function calling lets the application execute typed custom tools and
  return their results to the model. Structured outputs are intended for a
  schema-constrained final UI response.
- Gemini 3.6 Flash and Gemini 3.5 Flash-Lite are GA. Google positions 3.6 Flash
  for more complex agentic work and 3.5 Flash-Lite for high-throughput,
  lower-cost execution.
- Gemini can return thought summaries. Artha will not present raw or hidden
  chain-of-thought as a financial explanation; it will show a factual activity
  trail, assumptions, calculations and ledger evidence instead.
- Stripe's agent guidance recommends restricted credentials and sandbox/eval
  use because agent behavior is non-deterministic. Artha applies the stronger
  boundary of exposing **zero write tools** to the analyst.
- CFPB cash-flow guidance starts from tracked income, bills and savings. Artha's
  scenario engine therefore models dated cash movement and an explicit user
  buffer instead of issuing an unsupported “you can afford it” verdict.

Primary sources:

- [Gemini Interactions API](https://ai.google.dev/gemini-api/docs/interactions-overview)
- [Gemini function calling](https://ai.google.dev/gemini-api/docs/function-calling)
- [Gemini tools and structured outputs](https://ai.google.dev/gemini-api/docs/tools)
- [Gemini thinking and thought summaries](https://ai.google.dev/gemini-api/docs/thought-signatures)
- [Latest Gemini models](https://ai.google.dev/gemini-api/docs/latest-model)
- [Stripe agent toolkit security guidance](https://docs.stripe.com/agents)
- [CFPB cash-flow budget tool](https://files.consumerfinance.gov/f/documents/cfpb_your-money-your-goals_cash_flow_budget_tool_2018-11_ADA.pdf)
- [NotebookLM source-citation UX](https://support.google.com/notebooklm/answer/16179559)

## Agent framework decision

Use **Google Agent Development Kit (ADK)** for the demo/test-account Artha
Analyst implementation and its trajectory evaluations. Keep the August 13
production assistant on the current direct Gemini request path while the ADK
runtime is benchmarked behind a feature flag.

ADK is the best first fit because Artha is already Python/FastAPI and
Gemini-only, and ADK provides typed tools, agent/workflow orchestration, a local
development UI and an agent evaluation runner in the same Google stack.
LangGraph remains a documented alternative if Artha later needs provider
portability, long-running durable workflows or checkpointed human approvals.
Those capabilities do not justify another runtime and observability service for
the initial read-only analyst.

This is a framework choice, not permission to widen authority. The ADK agent
receives only server-owned read tools, never raw SQL or ledger-write tools. It
must keep the same two-model-turn, three-tool-call and twelve-second limits,
and it cannot move to personal-data production until the privacy and eval gates
pass.

Primary framework sources:

- [Google ADK Python quickstart](https://adk.dev/get-started/python/)
- [Google ADK agent evaluations](https://adk-labs.github.io/adk-docs/evaluate/)
- [LangGraph orchestration overview](https://docs.langchain.com/oss/python/langgraph/overview)

## Target architecture

```text
question + short server-signed query frame
                 |
                 v
       Gemini planner (read-only)
                 |
        typed tool calls, max 3
                 |
                 v
 server tools + deterministic calculators
                 |
        facts, assumptions, evidence IDs
                 |
                 v
 schema-constrained answer and UI recipe
                 |
                 v
      React-owned approved components
```

The LLM may select tools and parameters. FastAPI owns authentication, input
validation, time/call budgets and the tool catalogue. Postgres owns ledger
truth. React owns all rendering. No model HTML, JavaScript, SQL or arbitrary
component code is accepted.

## Initial read-only tool catalogue

| Tool | Purpose | Deterministic output |
| --- | --- | --- |
| `ledger_summary` | Balance, income, personal spend and shared position for a date range | Totals, range, filters and row counts |
| `spend_breakdown` | Explain spending by category, merchant/platform or account | Ranked buckets and evidence IDs |
| `compare_periods` | Compare two explicit periods | Current, previous, absolute delta and percentage delta |
| `search_transactions` | Find supporting ledger activity | Bounded transaction references and match reason |
| `shared_balance` | Explain household receivables/payables | Member-level balances and settlement basis |
| `observed_repeats` | Identify repeated historical activity | Frequency, median interval and confidence evidence |
| `project_cash_scenario` | Run best/base/worst cash-flow cases | Daily projected balance, low point and buffer gap |
| `card_payment_impact` | Show a user-entered card payment's cash effect | Funding balance, card outstanding and timing impact |

The first production tool set is limited to the existing ledger-summary and
transaction-evidence paths. Scenario tools remain demo-only until their
arithmetic and language gates pass.

## Scenario contract

Every scenario separates four kinds of information:

| Label | Meaning |
| --- | --- |
| **Actual** | Confirmed ledger facts |
| **Observed** | A pattern inferred deterministically from historical facts |
| **Assumption** | A future event or buffer explicitly supplied or edited by the user |
| **Projection** | Deterministic arithmetic produced from actuals plus assumptions |

Example questions:

- “If salary is 10 days late, how long will my cash last?”
- “Can I buy a ₹40,000 phone and keep a ₹1 lakh buffer?”
- “What happens if I pay ₹25,000 toward HDFC Card from ICICI?”
- “Show best, base and worst cash position for the next 60 days.”
- “What drove food spending up compared with last month?”

Artha does not answer “yes, you can afford it.” It shows the projected low
balance, the chosen buffer and the gap. Assumptions are editable before a rerun.
Current card metadata has outstanding balance, limit, statement day and due day,
but not the exact statement amount due; the tool must therefore use a
user-entered payment amount and say “current outstanding,” not “amount due.”

## Evidence-first generative UI

Every answer returns:

- resolved date range and filters;
- number of ledger movements used;
- calculation basis, for example “personal share; transfers excluded”;
- stable fact IDs for rendered metrics;
- matching transaction IDs;
- an expandable **How this was calculated** trail;
- a **View matching transactions** action;
- editable scenario assumptions when projections are present.

Approved React components:

- metric and delta card;
- comparison chart;
- ranked driver list;
- transaction evidence list;
- scenario table;
- assumptions panel;
- clarification and follow-up chips.

The visible activity trail uses factual steps such as “Compared July with June,”
“Checked 18 matching transactions” and “Projected 60 days using 4 assumptions.”
It never claims to reveal hidden reasoning.

## Conversation continuity

Artha continues to send Gemini requests with `store=false`. It will not rely on
provider-stored chat history. FastAPI may return a short-lived signed query frame
containing only:

- resolved range;
- metric;
- filters;
- comparison range;
- scenario assumptions.

This is sufficient to resolve “what about last month?” without repeatedly
sending the entire conversation or storing it with the provider.

## Operational limits

- Maximum 2 model turns and 3 read-only tool calls.
- Maximum 50 transaction evidence rows.
- Maximum 13-month analytical range for the first agent release.
- 10-second response target and 12-second hard deadline.
- One retry for a retryable provider failure within the same deadline.
- No background autonomous work, external web tools or MCP tools.
- No write tools, transaction drafts or investment recommendations in the first
  agent release.
- The model never receives credentials, direct database access or unrestricted
  account/member identifiers.

## Model strategy

Do not upgrade by opinion. Benchmark two current GA candidates on identical
fictional cases:

| Track | Candidate | Intended use |
| --- | --- | --- |
| Fast path | `gemini-3.5-flash-lite` | routing, extraction and simple one-tool questions |
| Analyst path | `gemini-3.6-flash` | comparison, driver analysis and bounded multi-tool scenarios |

Promotion requires better task success without breaching the same latency,
privacy, cost and safety thresholds. Model strings remain configuration, not
product architecture.

Other current text-capable candidates were considered and excluded from the
first benchmark:

| Model | Decision | Reason |
| --- | --- | --- |
| `gemini-3.5-flash` | Do not use | 3.6 Flash is the newer agentic model with the same paid input price and lower output price |
| `gemini-3.1-flash-lite` | Do not use | Older fast-path model; 3.5 Flash-Lite has already passed Artha's current gates |
| `gemini-3.1-pro-preview` | Do not use | Preview, paid-only and unnecessary for a bounded three-tool analyst |
| Live, image, audio and managed-agent models | Out of scope | Artha V1 needs server-side text/tool orchestration, not voice, media generation or a remote autonomous sandbox |

Current standard paid prices per million tokens are $0.30 input / $2.50 output
for 3.5 Flash-Lite and $1.50 input / $7.50 output for 3.6 Flash. Both currently
have a free tier, but Google's pricing page states that free-tier submitted
content is used to improve its products. Artha therefore uses free access only
for fictional/demo work; real personal-finance AI requires an approved paid
configuration.

## Evaluation programme

The agent is evaluated as a system, not only as prose.

### Offline synthetic suites

The first 30-case fictional contract is stored in
[`evals/agent-analyst-cases-v1.jsonl`](../../../evals/agent-analyst-cases-v1.jsonl)
with its fixed ledger in
[`evals/agent-analyst-context-v1.json`](../../../evals/agent-analyst-context-v1.json).

1. **Planner accuracy** — correct tool choice, arguments and call count.
2. **Entity/time resolution** — dates, accounts, categories, merchants and
   members, including Hinglish and Indian amount formats.
3. **Calculation equality** — every displayed number exactly equals SQL or the
   deterministic scenario engine.
4. **Evidence precision** — cited transactions support the answer and required
   supporting rows are not omitted.
5. **Follow-up continuity** — the signed query frame resolves “last month,”
   “only ICICI” and “exclude Zomato” correctly.
6. **Scenario arithmetic** — best/base/worst assumptions, dated cash movements,
   card payments and buffer gaps.
7. **Ledger semantics** — transfers, repayments, adjustments, corrected and
   voided rows never leak into personal spend incorrectly.
8. **Ambiguity/no data** — asks one useful clarification and invents no fact.
9. **Safety/adversarial** — prompt injection, attempted writes, arbitrary SQL,
   tool escalation and requests for investment/tax advice are rejected.
10. **Resilience** — timeouts, rate limits, malformed calls and partial tool
    failure return a truthful retry state.

### Required metrics

- end-to-end answer correctness;
- tool-selection and argument exactness;
- displayed-number equality;
- evidence precision/recall;
- unsupported-write attempt rate, target **0%**;
- hallucinated-ledger-fact rate, target **0%**;
- clarification quality;
- p50/p95 latency;
- model turns and tool calls per successful answer;
- input, output and thinking tokens per successful answer;
- estimated provider cost per successful answer.

### Online evaluation

- Demo/test accounts only at first.
- Log sanitized task/result metadata, never raw private questions or financial
  values without a separately approved private audit store.
- Compare answer usefulness, drill-down rate, retry rate and latency against the
  current fixed-intent baseline.
- A human reviews every failure cluster before adding a new tool or expanding
  the tool limit.

## Release sequence

### August 13 — trustworthy assistant slice

- Existing database-backed full-ledger search.
- Evidence date range, source count and matching-ledger drill-down for supported
  Ask Artha answers.
- Better contextual follow-up chips and truthful failure recovery.
- Deterministic **Use again** from a prior transaction into an unsaved draft.
- Agent schemas, scenario calculator and expanded evals behind the demo/test
  account flag only.

### Next sprint — Artha Analyst beta

- Google ADK planner with the first four read-only tools, calling Gemini through
  stateless, server-owned configuration.
- Short-lived signed query frame for follow-ups.
- Activity trail, evidence list and comparison UI.
- Gemini 3.5 Flash-Lite versus 3.6 Flash benchmark.
- Demo-only cash scenario tool with editable assumptions.

### Later

- Observed repeats and proactive review suggestions.
- User-approved private interaction/eval ledger with export and delete.
- Additional scenarios only after deterministic acceptance tests.
- No autonomous writes, money movement or portfolio advice without a separate
  product, security and regulatory decision.

## Interview demonstration

Use one fictional ledger and show this sequence:

1. Ask: “Why did food spending increase this month?”
2. Show the planner call `compare_periods`, then `spend_breakdown`.
3. Render the database-calculated delta and top drivers.
4. Open the exact matching transactions from the evidence card.
5. Ask: “If I also spend ₹40,000 on a phone, can I keep a ₹1 lakh buffer?”
6. Edit one assumption and rerun best/base/worst projections.
7. Open the eval dashboard: tool accuracy, numeric equality, evidence precision,
   latency, tokens, cost and zero write attempts.

That demonstrates agent planning, tool use, memory, generative UI, financial
semantics, privacy boundaries and evaluation—not just a chatbot wrapper.
