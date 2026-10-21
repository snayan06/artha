import type { Paise } from '../types'

const moneyFormatter = new Intl.NumberFormat('en-IN', {
  style: 'currency',
  currency: 'INR',
  minimumFractionDigits: 0,
  maximumFractionDigits: 2
})

export function formatMoney(paise: Paise, options?: { sign?: boolean }): string {
  const rupees = paise / 100
  const formatted = moneyFormatter.format(Math.abs(rupees)).replace('₹', '₹')
  if (!options?.sign || paise === 0) return paise < 0 ? `−${formatted}` : formatted
  return paise > 0 ? `+${formatted}` : `−${formatted}`
}

export function rupeesToPaise(rupees: number): Paise {
  const paise = Math.round(rupees * 100)
  return Number.isFinite(paise) && Number.isSafeInteger(paise) ? paise : 0
}
