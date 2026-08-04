export function formatLocalDate(date: Date): string {
  const year = date.getFullYear()
  const month = String(date.getMonth() + 1).padStart(2, '0')
  const day = String(date.getDate()).padStart(2, '0')
  return `${year}-${month}-${day}`
}

export function localDateOffset(days: number, from = new Date()): string {
  const date = new Date(from.getFullYear(), from.getMonth(), from.getDate() + days)
  return formatLocalDate(date)
}

const monthNumbers: Record<string, number> = {
  jan: 0, january: 0, feb: 1, february: 1, mar: 2, march: 2, apr: 3, april: 3,
  may: 4, jun: 5, june: 5, jul: 6, july: 6, aug: 7, august: 7, sep: 8,
  sept: 8, september: 8, oct: 9, october: 9, nov: 10, november: 10, dec: 11, december: 11
}

export function parseLocalDatePhrase(input: string, now = new Date()): string {
  const normalized = input.toLowerCase()
  const iso = input.match(/\b(\d{4}-\d{2}-\d{2})\b/)?.[1]
  if (iso) return iso
  const relativeDays = normalized.match(/\b(\d+)\s+days?\s+(?:ago|back)\b/)
  if (relativeDays) return localDateOffset(-Number(relativeDays[1]), now)
  if (/day before yesterday/.test(normalized)) return localDateOffset(-2, now)
  if (/\byesterday\b/.test(normalized)) return localDateOffset(-1, now)
  if (/\btoday\b/.test(normalized)) return localDateOffset(0, now)

  const named = normalized.match(/\bon\s+(\d{1,2})\s+(jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|jul(?:y)?|aug(?:ust)?|sep(?:t(?:ember)?)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)\b/)
  if (named) {
    const day = Number(named[1])
    const month = monthNumbers[named[2]]
    const date = new Date(now.getFullYear(), month, day)
    if (date.getMonth() === month && date.getDate() === day) return formatLocalDate(date)
  }
  return localDateOffset(0, now)
}
