# LLM usage map and safety boundary

Date: 7 August 2026
Status: Gemini production paths implemented and deployed for the private pilot

## Current production usage

| Feature | Gemini job | Code-owned boundary | Failure behavior | May write? |
| --- | --- | --- | --- | --- |
| Quick Add | Interpret authenticated natural text into a proposed structured draft | Strict Pydantic schema; account/member/category allow-lists; integer paise; date and split validation | Preserve exact text and open the manual form | No |
| Auto-tagging | Suggest one existing category | Caller supplies description/amount/direction only; server loads up to 200 authenticated household categories and validates the returned ID/name pair | Return no suggestion | No |
| Assistant | Select a supported intent and copy its exact approved narrative/widget bundle | Server owns titles, labels, values, rows, points, order and cardinality; strict equality validation; React-owned rendering | Sanitized `503` and honest UI error | No |

The current pilot configuration is `gemini-3.5-flash-lite`, called server-side
through Google's official SDK. Explicit Ollama selection is available only for
local developer use; it is not a production provider or a production fallback.

## Quick Add decision flow

```text
User text
   │
   ▼
Authenticated household context and allowed IDs
   │
   ▼
Gemini strict interpretation
   ├── valid ─► schema + allow-list + money/split validation
   │                      │
   │                      ▼
   │              unsaved review draft ─► user edits/confirms ─► ledger RPC
   │
   └── unavailable, unsure or invalid
                          │
                          ▼
                preserve exact source text
                   + open manual form
                  no guess, no write
```

Gemini may interpret phrases such as `25k`, `three days ago`, account aliases
and transfer direction. It may not invent an account, member or category,
calculate an authoritative balance, bypass confirmation or alter the ledger.
Production recovery never substitutes the local demo/evaluation parser.

Production Quick Add and production tag suggestion call Gemini without loading
`merchant_rules`. For the standalone tag endpoint, FastAPI—not the caller—loads
up to 200 active, direction-eligible categories from the authenticated household
and supplies that allow-list to the model. The V1 web app does not call this
endpoint; its Quick Add category is separate capture output. Merchant-rule-first
matching and prospective learning exist on the local SQLAlchemy demo path;
Supabase production integration remains planned. An explicit allow-list remains
available only to the internal local/demo contract for isolated testing.

## Assistant value flow

1. FastAPI creates a bounded authenticated snapshot containing total balance,
   current-month spending/income, up to 20 member balances, 5 categories, 6
   monthly points and 8 recent transaction summaries.
2. Server code creates one exact canonical widget bundle for each intent:
   `summary`, `spending`, `income`, `cashflow`, `shared`, `transactions`,
   `clarification` and `unsupported`.
3. Gemini selects an intent and copies its approved narrative and widget array.
4. FastAPI requires exact equality for narrative, titles, labels, values, rows,
   points, order and cardinality.
5. React renders repository-owned components.

Model-authored HTML, arbitrary numeric prose and ledger changes are outside the
contract. An invalid response is unavailable, not a partial answer.

## Implementation and evaluation

- Provider and strict schemas: `apps/api/src/artha_api/assistant.py`
- Production capture orchestration: `apps/api/src/artha_api/production_routes.py`
- Assistant and provider contracts: `apps/api/tests/test_assistant.py`
- Fictional capture dataset: `evals/capture-parser-v1.jsonl`
- Dataset contract checker: `scripts/check_capture_evals.py`

Dated benchmark artifacts may retain earlier provider baselines as historical
evidence. They do not describe the active production runtime.
