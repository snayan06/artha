import { describe, expect, it, vi } from 'vitest'
import { parseCaptureLocally } from './capture'
import { formatMoney, rupeesToPaise } from './money'

describe('local capture parser', () => {
  it('creates an unsaved equal-split draft using integer paise', () => {
    vi.setSystemTime(new Date('2026-08-04T08:00:00Z'))
    const draft = parseCaptureLocally('Paid 1,840 for groceries from HDFC UPI, split equally with Sam', [{ id: '7', name: 'Sam' }])

    expect(draft.kind).toBe('debit')
    expect(draft.amountPaise).toBe(184_000)
    expect(Number.isInteger(draft.amountPaise)).toBe(true)
    expect(draft.category).toBe('Groceries')
    expect(draft.account).toBe('HDFC UPI')
    expect(draft.memberSplits).toEqual([{ memberId: '7', memberName: 'Sam', amountPaise: 92_000 }])
  })

  it('recognises income language', () => {
    const draft = parseCaptureLocally('Received ₹45,000 salary in ICICI Bank')
    expect(draft.kind).toBe('credit')
    expect(draft.amountPaise).toBe(4_500_000)
    expect(draft.category).toBe('Salary')
  })

  it('interprets 25k self transfer with ordered source and destination accounts', () => {
    const draft = parseCaptureLocally('self transfer 25k ICICI -> HDFC', [], [
      { id: 'hdfc-id', name: 'HDFC Bank', kind: 'bank' },
      { id: 'icici-id', name: 'ICICI Bank', kind: 'bank' }
    ])

    expect(draft).toMatchObject({
      kind: 'transfer',
      amountPaise: 2_500_000,
      category: 'Transfer',
      account: 'ICICI Bank',
      sourceAccountId: 'icici-id',
      destinationAccount: 'HDFC Bank',
      destinationAccountId: 'hdfc-id',
      confidence: 'high'
    })
    expect(draft.memberSplits).toEqual([])
  })

  it('supports Indian lakh shorthand', () => {
    const draft = parseCaptureLocally('transfer 1.5 lakh from ICICI Bank to HDFC UPI')
    expect(draft.kind).toBe('transfer')
    expect(draft.amountPaise).toBe(15_000_000)
  })

  it('backdates without leaking the date phrase into the description', () => {
    vi.setSystemTime(new Date('2026-08-04T08:00:00Z'))
    const draft = parseCaptureLocally('paid 850 for dinner 3 days ago from HDFC UPI')

    expect(draft.occurredAt).toBe('2026-08-01')
    expect(draft.merchant).toBe('dinner')
  })
})

describe('money helpers', () => {
  it('converts at the display boundary and formats Indian rupees', () => {
    expect(rupeesToPaise(1840.25)).toBe(184_025)
    expect(formatMoney(184_025)).toBe('₹1,840')
  })

  it('rejects non-finite and unsafe browser amounts at the input boundary', () => {
    expect(rupeesToPaise(Number.POSITIVE_INFINITY)).toBe(0)
    expect(rupeesToPaise(Number.NaN)).toBe(0)
    expect(rupeesToPaise(Number.MAX_SAFE_INTEGER)).toBe(0)
  })
})
