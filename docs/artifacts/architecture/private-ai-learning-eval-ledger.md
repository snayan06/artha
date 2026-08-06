# Private AI learning and evaluation ledger

Date: 6 August 2026  
Priority: immediate follow-up after the hosted-model decision

## Purpose

Give Artha an auditable record of how natural-language capture, auto-tagging and
assistant interpretation behaved, what the user ultimately confirmed, and which
sanitized examples should become regression tests. This is a private product
learning loop, not automatic external model training.

## Privacy contract

- Explain the learning history during onboarding and keep a Settings control to
  disable future collection, export it, or permanently delete it.
- Never store API keys, authorization headers, provider response bodies,
  reasoning text, emails, account numbers or model-generated prose.
- Original user text and reviewed JSON remain private to the owning household,
  protected by database RLS. They are never placed in Git or public artifacts.
- Turning collection off stops new records; it does not affect normal ledger use.
- No record may be copied to an external training service or public dataset
  without a separate explicit consent flow.

## Proposed tables

### `ai_interactions`

One row per model or deterministic interpretation attempt.

| Column | Purpose |
| --- | --- |
| `id uuid primary key` | Stable audit identifier |
| `household_id uuid not null` | RLS ownership boundary |
| `actor_user_id uuid not null` | Authenticated user who initiated it |
| `feature text not null` | `capture`, `auto_tag` or `assistant` |
| `input_text text` | Private original input; null when collection is disabled |
| `provider text`, `model text` | Exact inference identity |
| `prompt_version text`, `schema_version text` | Reproducibility |
| `proposed_json jsonb` | Constrained, validated model/deterministic result |
| `outcome text not null` | `draft`, `clarify`, `reject`, `fallback` or `error` |
| `failure_kind text` | Sanitized rate-limit/timeout/schema/grounding class |
| `attempts smallint`, `latency_ms integer` | Reliability measurement |
| `created_at timestamptz` | Cursor pagination and retention |

Constraints limit enumerations, positive attempt counts and non-negative
latencies. JSON is stored only after Pydantic validation and allow-list grounding.

### `ai_interaction_reviews`

Append-only record of what the user changed or confirmed.

| Column | Purpose |
| --- | --- |
| `id uuid primary key` | Review identifier |
| `interaction_id uuid not null` | Indexed FK to `ai_interactions` |
| `household_id uuid not null` | Direct RLS/index boundary |
| `reviewer_user_id uuid not null` | Authenticated reviewer |
| `review_action text not null` | `confirmed`, `corrected` or `discarded` |
| `confirmed_json jsonb` | Validated reviewed result; null for discard |
| `changed_fields text[]` | Constrained field names only |
| `created_at timestamptz` | Append-only audit order |

The app never mutates an old review. The newest `(created_at, id)` pair is the
cursor for history and export.

### `model_eval_runs` and `model_eval_cases`

Store benchmark metadata and constrained results separately from private user
history. Run rows contain dataset/model/prompt/schema versions, start/end time,
rate-limit budget and final decision. Case rows contain case ID, tags, expected
JSON, actual constrained JSON, pass/fail/unavailable, failure kind, attempts and
latency. Versioned fictional inputs remain in Git; real household text does not.

## Security and indexes

- Enable and force RLS on private interaction and review tables.
- Owner policy uses indexed `household_id` membership and `(select auth.uid())`.
- Add indexes on both foreign keys and on
  `(household_id, created_at desc, id desc)` for cursor-based history/export.
- Revoke direct anonymous access. Writes go through authenticated server/RPC
  validation; the service-role key is never available to the browser.
- Deletion removes the owning household's interaction/review rows atomically and
  writes no copy to application logs.

## Promotion into evaluation cases

1. User reviews or corrects a private interaction.
2. A local/admin-only tool removes names, merchants, dates, balances and IDs.
3. The sanitized example is shown for human approval.
4. Only the approved fictional form is added to a versioned JSONL dataset.
5. CI validates structure; hosted model runs remain separate and checkpointed.

There is no automatic path from a production row to Git or a training provider.

## Rate-limit-aware evaluation requirements

- Read request/token limit headers and persist only numeric remaining/reset data.
- Budget against RPM, RPD, TPM and TPD before sending the next request.
- Set bounded completion tokens so providers do not reserve an oversized quota.
- Checkpoint each constrained case atomically and resume only unavailable cases.
- Keep model correctness separate from provider availability in every report.
- Stop before exhaustion and show the next safe resume time rather than creating
  a burst of predictable `429` failures.
