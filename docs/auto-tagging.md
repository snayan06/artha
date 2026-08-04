# Auto-tagging design

Auto-tagging is a suggestion pipeline. It never posts or rewrites a transaction
without confirmation.

## Decision order

1. Normalize the merchant and description: lowercase, collapse whitespace, and
   remove payment-network noise that does not identify the merchant.
2. Match an active household `merchant_rules` entry by priority (`exact`, then
   `contains`, then carefully validated `regex`).
3. Apply safe built-in signals for obvious income, transfers, and settlements.
4. If the category is still unresolved, request a structured suggestion from
   the configured open-weight model.
5. Validate that the returned category already exists in the household and show
   its confidence and reason in the draft review.
6. Save only after the user confirms. When the user corrects the category, offer
   to remember that merchant-to-category rule for future drafts.

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

It does not receive account numbers, card numbers, database credentials, raw
household history, or arbitrary SQL access.

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

## Learning behavior

Learning is household-specific and prospective. A correction may create or
update a `merchant_rules` row, so later entries become deterministic and do not
consume model quota. Existing confirmed transactions are never silently
retagged. Bulk historical retagging, if added later, must be an explicit preview
and confirmation workflow.

## Provider behavior

The experimental private-pilot default is Qwen3.6-27B through Groq. Local/private
use can select Qwen3 4B through Ollama. Both providers implement the same
internal interface and strict response schema. When a provider is missing,
rate-limited, unavailable or returns invalid output, Artha falls back to manual
category selection without blocking transaction entry. A representative model
comparison is tracked in the backlog before any production model is locked.
