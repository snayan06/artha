import { describe, expect, it } from 'vitest'
import { formatLocalDate, parseLocalDatePhrase } from './date'

const now = new Date(2026, 7, 4, 0, 15)

describe('local transaction dates', () => {
  it.each([
    ['paid today', '2026-08-04'],
    ['paid yesterday', '2026-08-03'],
    ['paid day before yesterday', '2026-08-02'],
    ['paid 3 days ago', '2026-08-01'],
    ['paid 4 days back', '2026-07-31'],
    ['paid on 2 Aug', '2026-08-02'],
    ['paid on 2 August', '2026-08-02'],
    ['paid on 2026-07-29', '2026-07-29']
  ])('parses %s', (phrase, expected) => {
    expect(parseLocalDatePhrase(phrase, now)).toBe(expected)
  })

  it('formats the local calendar without UTC conversion', () => {
    expect(formatLocalDate(new Date(2026, 7, 4, 0, 5))).toBe('2026-08-04')
  })
})
