# Natural-language transfer review

Date: 4 August 2026  
Status: implemented and verified locally; production deployment pending

## User scenario

Fictional input:

```text
self transfer 25k ICICI -> HDFC
```

The review screen now proposes, without saving:

| Field | Proposed value |
| --- | --- |
| Movement | Transfer |
| Amount | ₹25,000 |
| Description | Self transfer |
| From | ICICI Bank |
| To | HDFC UPI |
| Date | Today |
| Family split | Hidden because internal transfers are not shared expenses |

The user can edit every field. Confirmation remains disabled when the source or
destination is missing or both accounts are the same.

## Interaction evidence

The local browser test found the expected accessible controls and values:

```text
Money transferred
Amount in rupees: 25000
Description: Self transfer
Category: Transfer
Transfer from account: ICICI Bank
Transfer to account: HDFC UPI
Nothing has been saved yet.
```

The dark-theme desktop render was visually inspected. A screenshot is not
committed because browser captures can accidentally contain private data; this
artifact uses only the fictional values above.

## Implementation

- Review page: `apps/web/src/pages/QuickAddPage.tsx`
- Deterministic capture fallback: `apps/web/src/lib/capture.ts`
- API mapping: `apps/web/src/lib/api.ts`
- Transaction presentation: `apps/web/src/components/TransactionRow.tsx`
- Capture tests: `apps/web/src/lib/capture.test.ts`

## Remaining acceptance

- Deploy and smoke-test the collapsed transfer history on the final domain.
- Add dedicated per-account activity pages.
- Recheck 320 px and 390 px layouts after the production build is deployed.
- Run the same scenario against hosted Qwen after its server-only key is added.
