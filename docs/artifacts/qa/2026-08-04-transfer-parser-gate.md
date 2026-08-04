# Transfer and capture-parser verification

Date: 4 August 2026  
Result: local automated gate passed

## Exact regression

Input: `self transfer 25k ICICI -> HDFC`

Expected and observed proposal:

- kind: transfer;
- amount: 2,500,000 paise (₹25,000);
- source: ICICI Bank;
- destination: HDFC UPI;
- no expense split;
- no write before confirmation.

## Full gate

| Check | Result |
| --- | --- |
| ESLint | Passed |
| TypeScript | Passed |
| Vitest | 71 passed |
| Ruff | Passed |
| strict mypy | Passed |
| pytest | 87 passed |
| Vite production build | Passed |
| Capture dataset contract | 50 cases valid |

The build produced a non-blocking warning for a JavaScript entry chunk above
500 kB. Code splitting is tracked as performance work; it did not fail the
release gate.

## Dataset composition

The fictional V1 set contains 39 expected drafts, 8 clarification cases and 3
rejections. It covers transfers, income, expenses, Indian shorthand (`k`, lakh,
crore), dates, cards, cash, wallets, family splits, Hinglish, typos, unsafe
amounts and ambiguous instructions.

This result validates the dataset format and gates 22 common/safety-critical
deterministic draft cases plus negative, amount-only and unknown-member safety checks. It is not
a hosted-Qwen accuracy score; that full 50-case benchmark remains blocked on
the server-only provider key.
