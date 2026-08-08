# GPT-OSS 20B cross-feature benchmark design

> **Superseded historical artifact — 7 August 2026.** This candidate design is
> retained only as pre-Gemini evaluation history. Artha production uses Gemini
> through Google's official server-side SDK. Groq and Qwen are not current
> providers or fallback paths; Ollama remains optional for local development only.

Date: 6 August 2026  
Candidate: `openai/gpt-oss-20b` through Groq

## Objective

Decide whether GPT-OSS 20B should become Artha's single hosted model for
natural-language capture, automatic category suggestions, and the read-only
assistant with generated UI.

The decision uses only fictional, versioned fixtures. Reports must not persist
model prose, keys, emails, real transaction text or real balances.

## Preserved safety architecture

- Deterministic parsing and merchant rules run before the hosted model.
- The model creates suggestions or unsaved drafts only and receives no write tool.
- Model-selected accounts, members and categories are checked against server allow-lists.
- Assistant totals come from deterministic context, never model arithmetic.
- Provider or validation failure falls back safely and never silently saves data.

## Integration

- Use `openai/gpt-oss-20b` as the shared Groq default while preserving the
  environment override.
- Use Groq strict JSON Schema output for capture, tagging and assistant results,
  with Pydantic and grounding as the final validation boundary.
- Respect `Retry-After`, use bounded retries, checkpoint completed cases and
  resume only unavailable cases.

## Benchmark suites

1. **Capture:** existing 50 fictional cases covering Indian amounts, dates,
   Hinglish, typos, transfers, splits, ambiguity and unsupported requests.
2. **Auto-tagging:** fictional clear, unknown, ambiguous, boundary and invented
   category cases.
3. **Assistant/UI:** fixed fictional financial context with balance, spend,
   income, cashflow, shared, transactions, clarification, unsupported and write
   attempt questions.
4. **Reliability/safety:** schema validity, latency, retries, provider failures,
   grounding violations, arbitrary UI/tool values and write attempts.

## Decision gates

| Gate | Required result |
| --- | --- |
| Coverage | 100% valid terminal results after bounded retries |
| Capture critical fields | 100% amount, kind, account and outcome accuracy |
| Capture complete cases | At least 96% |
| Clear auto-tags | At least 90% exact category accuracy |
| Ambiguous/unknown auto-tags | 100% no-suggestion; zero invented IDs |
| Assistant schema/tool boundary | 100% valid; zero arbitrary components/tools |
| Assistant financial values | 100% deterministic-context agreement |
| Write/grounding safety | Zero writes and zero invented account/member/category IDs |
| Provider reliability | Zero unresolved unavailable cases |

Pass every hard gate to adopt. A non-safety latency miss permits a conditional
private pilot with visible fallback. Any schema, numeric, grounding or safety
miss rejects the candidate and keeps hosted AI disabled.

## Evidence

Write sanitized Markdown and JSON reports for all three feature suites plus a
decision artifact. Run focused tests and the complete project gate. Benchmarking
does not deploy a key or enable hosted AI in production.
