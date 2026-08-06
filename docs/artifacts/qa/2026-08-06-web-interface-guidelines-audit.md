# Web Interface Guidelines audit

Date: 6 August 2026
Scope: `apps/web/index.html` and all production `apps/web/src/**/*.{tsx,css}`
Guideline source: [Vercel Web Interface Guidelines](https://raw.githubusercontent.com/vercel-labs/web-interface-guidelines/main/command.md)
Status: **local UI gate passes; production financial-use gate remains blocked by the authenticated ledger RPC**

This review combined a complete source audit with live browser checks. Only
fictional demo data was used. It does not replace authenticated production
acceptance.

## Fixed findings

### `apps/web/src/components/Shell.tsx`

- `apps/web/src/components/Shell.tsx:22` - added a keyboard-visible skip link and a stable main-content target.
- `apps/web/src/components/Shell.tsx:25` - logo navigation now uses a real link instead of an `onClick` button.
- `apps/web/src/components/Shell.tsx:29` - replaced the hardcoded month with `Intl.DateTimeFormat`.
- `apps/web/src/components/Shell.tsx:45` - bottom navigation now uses links, keeps 44 px+ targets and includes safe-area bottom padding.

### `apps/web/src/pages/LoginPage.tsx`

- `apps/web/src/pages/LoginPage.tsx:65` - email input now has `name`, `autocomplete`, correct type/input mode, disabled spellcheck and a visible focus replacement.
- `apps/web/src/pages/LoginPage.tsx:67` - submit remains available for native required-field validation and disables only during configuration failure or request loading.
- `apps/web/src/pages/LoginPage.tsx:71` - async errors use live regions and wrap long content.
- `apps/web/src/pages/LoginPage.tsx:81` - loading motion honors reduced-motion preferences.

### `apps/web/src/pages/OnboardingPage.tsx`

- `apps/web/src/pages/OnboardingPage.tsx:42` - validation errors move focus to an accessible error summary.
- `apps/web/src/pages/OnboardingPage.tsx:171` - native selects have names, explicit colors and autofill policy.
- `apps/web/src/pages/OnboardingPage.tsx:268` - generated fields have meaningful names, input modes, numeric steps, autofill policy and focus-visible treatment.

### `apps/web/src/pages/QuickAddPage.tsx`

- `apps/web/src/pages/QuickAddPage.tsx:39` - browser unload warns before losing an unsaved capture or review draft.
- `apps/web/src/pages/QuickAddPage.tsx:94` - in-app Back asks before discarding an unsaved draft.
- `apps/web/src/pages/QuickAddPage.tsx:129` - natural-language capture has a meaningful name, autofill policy, example placeholder and focus-visible state.
- `apps/web/src/pages/QuickAddPage.tsx:141` - parser/write errors are announced and safely wrap long content.
- `apps/web/src/pages/QuickAddPage.tsx:158` - amount uses a numeric input with decimal input mode and paise-safe step.

### `apps/web/src/components/SpendChart.tsx`

- `apps/web/src/components/SpendChart.tsx:6` - added an explicit empty state.
- `apps/web/src/components/SpendChart.tsx:11` - visual chart is paired with a screen-reader data table; information no longer depends on color or hover.
- `apps/web/src/components/SpendChart.tsx:16` - axes and series use theme-aware tokens; chart animation is disabled for predictable motion.
- `apps/web/src/components/SpendChart.tsx:32` - values use semantic row/column headers and tabular number formatting.

### `apps/web/src/pages/AssistantPage.tsx`

- `apps/web/src/pages/AssistantPage.tsx:55` - model-loading updates use status semantics and reduced-motion support.
- `apps/web/src/pages/AssistantPage.tsx:75` - long user/model text wraps safely.
- `apps/web/src/pages/AssistantPage.tsx:82` - generated tables have captions, column scopes and tabular numbers.
- `apps/web/src/pages/AssistantPage.tsx:83` - generated charts have theme-aware colors, no motion dependency, an empty state and a screen-reader data table.

### `apps/web/src/index.css` and `apps/web/index.html`

- `apps/web/src/index.css:10` - light/dark `color-scheme` and chart color tokens are explicit.
- `apps/web/src/index.css:24` - dark native controls and chart tokens use the dark palette.
- `apps/web/src/index.css:62` - touch manipulation, safe-area utilities and reduced-motion fallback are present.
- `apps/web/index.html:8` - font origins are preconnected; the render-blocking CSS `@import` was removed.
- `apps/web/index.html:19` - browser theme color now follows the resolved light/dark theme.

Decorative Lucide icons across all production components now explicitly use
`aria-hidden="true"`. Icon-only actions retain accessible names.

## Live responsive matrix

| Viewport | Routes checked | Theme | Result |
| --- | --- | --- | --- |
| 320 × 740 | Home | Light | Pass: 320 px document width, no horizontal overflow |
| 390 × 844 | Home, Transactions, Shared, Assistant, Quick Add | Light | Pass: every route remained 390 px wide with no page overflow |
| 390 × 844 | Quick Add | Dark | Pass: dark native controls, theme meta and surfaces; no overflow |
| 1440 × 900 | Home | Dark | Pass: centered laptop layout; no horizontal overflow |

Visual inspection covered the mobile Home, mobile Quick Add in both themes and
the laptop Home. Automated tests cover onboarding, auth recovery, transactions
and error states. A final authenticated production matrix is still required.

## Remaining findings

### `apps/web/src/pages/TransactionsPage.tsx`

- `apps/web/src/pages/TransactionsPage.tsx:11` - search/filter/account state is not reflected in the URL; add query-parameter state when shareable/deep-linked ledger views become a product requirement.
- `apps/web/src/pages/TransactionsPage.tsx:54` - transaction rows are not virtualized; add server pagination or virtualization before rendering more than 50 rows at once.

### `apps/web/src/pages/OnboardingPage.tsx`

- `apps/web/src/pages/OnboardingPage.tsx:69` - focused error summary is accessible, but validation is not yet rendered beside each invalid field. Add per-field messages before calling onboarding accessibility complete.

### Product copy exception

Artha retains sentence-case conversational headings and buttons instead of the
guideline's Title Case recommendation. This is an intentional product-voice
choice, not an accessibility defect.

## Verification

- Web TypeScript: pass.
- Web ESLint: pass.
- Web tests: pass after this audit, including chart data-table and empty-state coverage.
- Manual horizontal-overflow checks: pass at 320, 390 and 1440 CSS px for the routes listed above.
- Production readiness: **not approved for real financial data** until the live authenticated ledger RPC and final-domain acceptance matrix pass.
