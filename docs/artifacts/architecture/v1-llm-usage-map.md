# LLM usage map and safety boundary

Date: 7 August 2026
Status: Gemini production paths implemented and deployed for the private pilot

## Current production usage

| Feature | Gemini job | Code-owned boundary | Failure behavior | May write? |
| --- | --- | --- | --- | --- |
| Quick Add | Interpret authenticated natural text into a proposed structured draft | Strict Pydantic schema; account/member/category allow-lists; integer paise; date and split validation | Preserve exact text and open the manual form | No |
| Auto-tagging | Suggest one existing category when no learned merchant rule matches | Rule lookup first; returned category ID must already belong to the household | Leave category for manual selection | No |
| Assistant | Select a supported intent, approved qualitative narrative and allow-listed widgets | Database supplies financial values and source IDs; strict response union; React-owned rendering | Sanitized `503` and honest UI error | No |

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
calculate an authoritative balance, bypass confirmation or call a write tool.
Production recovery never substitutes the local demo/evaluation parser.

## Assistant value flow

1. Gemini selects a supported intent from the user's question.
2. Server-owned read functions query the authenticated ledger and calculate the
   requested values.
3. Gemini selects an intent-matched approved qualitative narrative and safe
   widget types around those values.
4. FastAPI validates the full response, including the narrative, widget union,
   source IDs and server-derived numeric values.
5. React renders repository-owned components.

Model-authored HTML, arbitrary numeric prose, SQL and write tools are outside
the contract. An invalid response is unavailable, not a partial answer.

## Implementation and evaluation

- Provider and strict schemas: `apps/api/src/artha_api/assistant.py`
- Production capture orchestration: `apps/api/src/artha_api/production_routes.py`
- Assistant and provider contracts: `apps/api/tests/test_assistant.py`
- Fictional capture dataset: `evals/capture-parser-v1.jsonl`
- Dataset contract checker: `scripts/check_capture_evals.py`

Dated benchmark artifacts may retain earlier provider baselines as historical
evidence. They do not describe the active production runtime.
