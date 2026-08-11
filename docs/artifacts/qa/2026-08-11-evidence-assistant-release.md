# Evidence-backed assistant release

Date: 11 August 2026  
Status: published; production database and non-mutating signed-in smoke checks passed

This report contains sanitized release evidence only. It excludes prompts,
questions, transaction text, account/member labels, balances, emails, UUIDs,
tokens and secrets.

## Published scope

- Ask Artha answers now include an exact date basis, source count, cap status
  and a bounded recent supporting sample.
- Every supporting row can open its exact owner-scoped ledger activity, even
  when that activity is outside the currently loaded history page.
- Expense and income evidence uses the owner's personal share; transfers and
  settlements use the ledger movement amount.
- Settlement-aware shared evidence and local/demo evidence use the same strict
  response contract as production.
- Settings shows compact, truthful AI/privacy loading, ready, unavailable and
  demo states.
- A 30-case fictional analyst acceptance dataset and Google ADK next-sprint
  plan are checked in. They are design/evaluation inputs, not a production
  agent runtime.
- The private WhatsApp history-import artifact is a post-launch plan only. Raw
  personal chat content was neither uploaded nor committed.

## Verification

| Check | Evidence | Result |
| --- | --- | --- |
| Complete local gate | ESLint, TypeScript, Ruff, strict mypy, Vitest, Pytest, production PWA build, SQL parsing and keyless contracts | PASS; 233 web and 311 API tests |
| AI contracts | 60 capture, 30 analyst schema, 30 tag, 24 assistant and 49 router cases | PASS |
| Documentation | local link checker and whitespace check | PASS |
| Independent release review | cumulative feature diff and release boundaries | PASS; no Critical or Important findings |
| Local responsive interaction | 390 x 844 Assistant evidence, exact drill-down and retry | PASS; no horizontal overflow or application console error |
| Production database migration | `20260811010000_exact_ledger_activity_detail.sql` on the exact Artha project | PASS |
| Production database behavior | rollback-only owner/isolation contract `008_exact_ledger_activity_detail.sql` | PASS; no fictional test identities remained |
| RPC hardening | stable security-definer function, authenticated execution only, anonymous execution denied | PASS |
| Main publication | PR [#37](https://github.com/snayan06/artha/pull/37) merged as `b61858c` | PASS |
| Main CI and CodeQL | [CI](https://github.com/snayan06/artha/actions/runs/31518001200) and [CodeQL](https://github.com/snayan06/artha/actions/runs/31518001192) | PASS |
| Exact-SHA deployment | Vercel web and API statuses attached to `b61858c` | PASS |
| Signed-in production smoke | Home, compact Settings disclosure and Assistant composer loaded without a write | PASS |

## Deployment safety note

The locally authenticated Supabase CLI account did not have access to the
project used by the deployed app. Production was therefore resolved from the
live application and changed only through the signed-in dashboard for that
exact project. The migration history, function catalog, privilege boundary and
rollback-only behavior were verified after publication.

The earlier CLI-linked project had already received four additive reviewed
migrations before the target mismatch was identified. No rows were deleted or
rewritten by those migrations. Future linked releases must pass the repository's
exact-project-ref guard before any database command.

## Release boundary

The evidence-backed fixed-intent assistant is deployed. A fully agentic
assistant, model-executed scenario suite and private WhatsApp history import are
not part of this release. Real family-finance text must still stay out of the
sample-only AI mode until the private-data AI gate is approved; manual ledger
entry remains the private path.
