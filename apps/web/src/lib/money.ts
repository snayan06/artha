import type { Paise } from '../types'

const compactFormatter = new Intl.NumberFormat('en-IN', {
  style: 'currency',
  currency: 'INR',
  maximumFractionDigits: 0
})

export function formatMoney(paise: Paise, options?: { sign?: boolean }): string {
  const rupees = paise / 100
  const formatted = compactFormatter.format(Math.abs(rupees)).replace('₹', '₹')
  if (!options?.sign || paise === 0) return paise < 0 ? `−${formatted}` : formatted
  return paise > 0 ? `+${formatted}` : `−${formatted}`
}

export function rupeesToPaise(rupees: number): Paise {
  return Math.round(rupees * 100)
}
