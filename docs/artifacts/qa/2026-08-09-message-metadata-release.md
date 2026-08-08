# Message UX and structured metadata release evidence

Date: 9 August 2026
Production commit: `e32b5b60b5575be9019d9253381ed4400be7a097`
Status: PRs #23/#24 merged and deployed; signed-in user acceptance remains

## Product scope

- Enter submits a non-empty Quick Add or Ask Artha message; Shift+Enter keeps a
  newline and IME composition Enter is ignored.
- Quick Add never confirms from the keyboard. Every financial write still needs
  the explicit confirmation action.
- Incomplete safe capture returns one server-owned question, grounded account
  choices where available, and safe full-form recovery while preserving the
  original text.
- Review separates the primary category from merchant, platform, subcategory,
  bounded context and optional explicit tags.
- Household merchant rules take precedence over the safe catalog, which takes
  precedence over an allow-listed model suggestion.
- Quick Add and Ask Artha show truthful progress messages. They do not expose
  Gemini private chain-of-thought.
- Confirmation strips raw source text, marks the remaining evidence reviewed,
  revalidates it in FastAPI and stores versioned metadata through the existing
  atomic transaction RPC.

## Automated evidence

Fresh `make check` for the combined release:

- Web: 20 files, 206 tests passed.
- API: 275 tests passed.
- ESLint, TypeScript, Ruff and strict mypy passed.
- Production PWA build passed.
- Eight migrations, seed and four SQL contract files parsed.
- AI contracts: 60 capture, 30 category-suggestion and 24 assistant cases valid
  without calling a model.

Focused feature evidence:

- Web message/metadata adapter and pages: 95 checks passed.
- API assistant, production routes and metadata: 122 checks passed.
- Metadata capture evaluation: 10 evaluation-runner tests passed and 60 cases
  validated.
- Independent branch review findings were corrected before publication:
  descending merchant-rule priority, category-correction provenance, strict
  confirmation metadata/tag validation, accurate clarification actions, and
  optional platform/subcategory clearing now have regression coverage.

The replacement Gemini key is stored locally in the ignored root `.env` and as
Sensitive Vercel Production and Preview variables; it is never written to this
repository. The hosted 60-case run initially reached the 15-request free-tier
quota. That exposed and fixed the newer Interactions SDK error boundary: rate
limits, timeouts and connection failures now become sanitized retryable capture
diagnostics or the normal unavailable state, never a raw provider exception.

The rate-limited rerun then completed all 60 cases with 100% provider
availability. Exact-case accuracy was 50/60 (83.3%) and structured-field
accuracy was 94.3%. Amounts were 48/48, kinds 48/48, source accounts 48/48 and
destination accounts 9/9. The ten exact misses were concentrated in metadata
display/canonicalization and one missing-account clarification. The affected
path now compares labels case-insensitively, stores one canonical display form,
derives only allow-listed attributes/tags explicit in the source, lets the safe
platform catalog own order-channel values, and instructs Gemini never to default
an unmentioned account. A hosted targeted rerun passed 8/10 raw model cases on
its first pass; the two raw omissions are both filled by the tested server-owned
canonicalization layer before review. The combined full hosted rerun and
deployed acceptance remain release gates.

## Persistence and privacy

The release uses the existing RLS-protected `transactions.metadata` object, so
no database migration is required. The existing recovery export/restore already
preserves that object. Relational household tags, aliases, indexes and metadata
analytics remain a separate data sprint.

No raw capture sentence is included in confirmation metadata, evaluation
checkpoints or reports. The designated demo account remains server-verified;
ordinary authenticated users use their own ledger.

## Rendered QA

Completed locally before publication:

- All six primary pages fit at 320 px and 1440 px; the 390 px Quick Add review
  also fits. Explicit light and dark switching passed with zero horizontal
  overflow.
- Quick Add produced an editable unsaved review on the local demo ledger. A
  prior manual pass also confirmed a reviewed ₹680 expense and verified the
  resulting dashboard movement.
- Ask Artha rendered its truthful progress state, recovered from a deliberately
  unavailable provider, restored the exact question and returned to `scrollY=0`
  at 390 px.
- The final clean-browser sweep reported no app-owned console warnings or
  errors. Keyboard behavior, metadata review, safe tag selection and live-region
  semantics are covered by the 206 web checks.

The production Gemini metadata result still requires signed-in final-domain
user acceptance.

## Remote release evidence

- PRs #23 and #24 are merged as `e32b5b6`.
- Main CI `31278245585` and CodeQL `31278245587` passed.
- Exact-SHA web and API Vercel deployments are Ready.
- Public web, API health, protected intent endpoint and production mobile login
  smoke checks passed.
- Isolated fictional browser QA passed routed capture, routed Ask Artha and the
  mixed-intent choice at mobile and desktop widths.

Pending: signed-in final-domain user acceptance, combined hosted capture rerun
and the named real-data release guards in the
[production release report](2026-08-09-unified-entry-production-release.md).

## Next sprint plan

1. Relational household tags, aliases, lifecycle controls and query indexes.
2. Merchant/platform/category personal-share aggregates and new canonical Ask
   Artha breakdown widgets.
3. Immediate **View transaction** and audited edit/soft-delete recovery.
4. Accounts & family maintenance, followed by invitation authorization.
5. Investments planning for mutual funds and stocks.
6. Dedicated planning for a bounded, read-only multi-step Ask Artha agent; no
   agent runtime is part of this release.
