# Auto-tagging design

Auto-tagging is a suggestion pipeline. It never posts or rewrites a transaction
without confirmation.

## Current production behavior

Supabase production Quick Add sends the authenticated capture context directly
to Gemini, including the household's existing category allow-list. It does not
currently load or apply `merchant_rules` before interpretation.

The production tag-suggestion endpoint is also Gemini-only today:

1. Send the minimum merchant/description context and existing category IDs.
2. Validate that Gemini selected an exact allow-listed category.
3. Present the suggestion in the unsaved review flow.
4. If Gemini is missing, unavailable or invalid, leave category selection to
   the user. Never create a fallback category.

Only explicit transaction confirmation can save the reviewed draft.

## Local/demo rule behavior

The SQLAlchemy local/demo path implements merchant-rule-first behavior. It
normalizes merchant text, matches household rules by `exact`, `contains`, then
validated `regex`, and asks the configured model only when no rule matches. A
confirmed correction can prospectively create or update a rule for later local
entries.

Production Supabase integration for matching and learning these rules is
planned. Until it ships, rule-first categorization must not be presented as a
production capability.

## Model input

The model receives only the minimum needed fields:

```json
{
  "merchant": "reliance fresh",
  "description": "weekly groceries",
  "direction": "expense",
  "amount_paise": 184000,
  "allowed_categories": ["Groceries", "Dining", "Transport", "Utilities"]
}
```

It does not receive account numbers, card numbers, database credentials or raw
household history.

## Model output

```json
{
  "category": "Groceries",
  "confidence": 0.96,
  "reason": "The merchant is a grocery retailer."
}
```

The API rejects unknown categories, malformed JSON, and out-of-range confidence.
A high-confidence result is preselected but remains an unsaved draft. A lower
confidence result is presented as a suggestion or clarification question.

## Learning contract

Where learning is enabled on the local/demo path, it is household-specific and
prospective. Existing confirmed transactions are never silently retagged. The
planned production integration must preserve the same rule: corrections affect
future suggestions only, and any bulk historical retagging requires an explicit
preview and confirmation workflow.

## Provider behavior

The production private pilot uses `gemini-3.5-flash-lite` through Google's
official SDK. Gemini receives an allow-list and may select only an existing
category. When it is missing, rate-limited, unavailable or invalid, Artha leaves
the category for manual selection without blocking transaction entry. Explicit
Ollama selection may be used in local development, but it is not a production
provider or recovery path.

Gemini requests use `store=false`; provider storage does not replace Artha's
household-scoped, consent-controlled audit design.
