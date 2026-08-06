# Gemini provider evaluation and safety decision

Date: 6 August 2026  
Candidate: `gemini-3.5-flash-lite` through the official `google-genai` SDK  
Decision: adopt for the fictional-data pilot and preview deployment

## Scope

The same provider adapter was evaluated across every current hosted-AI feature:

- natural-language capture into an unsaved review draft;
- allow-listed auto-tag suggestions;
- read-only assistant answers with approved inline metric, chart, table,
  insight and clarification components.

The datasets contain fictional accounts, people and balances. No real household
text or provider response body is committed to Git.

## Final release-gate results

| Feature | Result | Safety and grounding |
| --- | --- | --- |
| Capture parser | 50/50 cases; 227/227 compared fields | 39 amounts, 12 dates, 39 source accounts, 9 destination accounts, 8 clarifications and 3 rejections all correct |
| Auto-tagging | 30/30 cases | 100% clear-category accuracy, 100% safe-null accuracy, zero allow-list violations |
| Assistant UI | 24/24 cases | 100% numeric accuracy, 100% write/privacy/injection safety, 100% required component selection |

The final hosted runs had full coverage and no provider-unavailable cases. The
auto-tag run measured 1.369 s p50 / 1.521 s p95 latency; the assistant run
measured 1.322 s p50 / 1.584 s p95 latency. Capture requests were paced at 2.1
seconds to respect the project-specific free-tier quota.

Local report names:

- `capture-model-20260806T183537Z.json`
- `tag-model-20260806T180347Z.json`
- `assistant-model-20260806T181756Z.json`

Generated reports stay ignored because repeated hosted runs are local evidence;
this artifact records the reviewed result and the versioned fictional JSONL
datasets remain the reproducible input.

## Prompt and validation boundary

The system prompts explicitly define Indian amount shorthand, backdated and
ambiguous dates, account-to-account transfers, person payments, shared members,
unsupported lending/borrowing/EMIs, category semantics, exact clarification
field names and read-only assistant behavior.

Gemini never writes to the ledger. Capture produces an unsaved draft requiring
review and confirmation. Tag output must match an existing category ID/name
pair. Assistant output is JSON-only and is parsed into Artha's Pydantic
discriminated union; arbitrary HTML, JavaScript, SQL and unknown components are
rejected.

Gemini's hosted schema subset rejects the assistant's multi-widget discriminated
union. That path therefore uses JSON MIME mode and applies the full union
validation locally. The simpler capture and tagging paths use hosted structured
schemas plus the same local validation and allow-list grounding.

## Privacy and audit decision

- Interactions are sent with `store=false`.
- The API key remains server-only and is redacted from configuration
  representations and diagnostics.
- Google's free tier may use submitted content to improve products. The free
  tier is approved only for fictional evaluation; real family finance requires
  an appropriate paid privacy configuration or a local provider.
- Provider logs are not Artha's audit record. The household-scoped interaction,
  review and evaluation tables are specified in
  `private-ai-learning-eval-ledger.md` and remain a priority implementation item.
- Provider failure falls back to deterministic/manual behavior and never blocks
  ledger capture.

## Reproduce

With a server-only Gemini key in the ignored root `.env`:

```bash
make eval-feature-hosted
make eval-capture-hosted
make check
```

Only the keyless validators run in CI. Hosted benchmarks are deliberately
separate so pull requests never require or expose a provider credential.
