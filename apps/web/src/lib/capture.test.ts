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
})

describe('money helpers', () => {
  it('converts at the display boundary and formats Indian rupees', () => {
    expect(rupeesToPaise(1840.25)).toBe(184_025)
    expect(formatMoney(184_025)).toBe('₹1,840')
  })
})
