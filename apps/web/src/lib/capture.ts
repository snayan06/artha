import type { HouseholdMember, LedgerAccount, TransactionDraft } from '../types'
import { rupeesToPaise } from './money'
import { parseLocalDatePhrase } from './date'

const CATEGORY_RULES: Array<[RegExp, string]> = [
  [/grocer|reliance|vegetable|milk/i, 'Groceries'],
  [/dinner|lunch|breakfast|food|cafe|coffee|swiggy|zomato/i, 'Food & dining'],
  [/uber|ola|auto|cab|fuel|petrol/i, 'Transport'],
  [/rent/i, 'Rent'],
  [/salary|paycheck/i, 'Salary'],
  [/movie|netflix|spotify/i, 'Entertainment'],
  [/electric|internet|wifi|mobile|bill/i, 'Bills']
]

const DEMO_ACCOUNTS: LedgerAccount[] = [
  { id: 'demo-hdfc-upi', name: 'HDFC UPI', kind: 'bank' },
  { id: 'demo-icici-bank', name: 'ICICI Bank', kind: 'bank' },
  { id: 'demo-cash', name: 'Cash', kind: 'cash' },
  { id: 'demo-hdfc-card', name: 'HDFC Card', kind: 'credit_card' }
]

function amountInRupees(match: RegExpMatchArray | null, input: string): number {
  if (!match) return /\bone\s+crore\b/i.test(input) ? 10_000_000 : 0
  const value = Number(match[1].replaceAll(',', ''))
  const suffix = match[2]?.toLowerCase()
  const multiplier = suffix === 'k' || suffix === 'thousand'
    ? 1_000
    : suffix === 'l' || suffix === 'lac' || suffix === 'lakh'
      ? 100_000
      : suffix === 'cr' || suffix === 'crore'
        ? 10_000_000
      : 1
  return value * multiplier
}

function accountMention(input: string, account: LedgerAccount): { index: number; score: number } {
  const normalized = input.toLowerCase()
  const normalizedName = account.name.toLowerCase()
  const exact = normalized.indexOf(normalizedName)
  if (exact >= 0) return { index: exact, score: 3 }
  const accountTokens = normalizedName.split(/[^a-z0-9]+/).filter(Boolean)
  if (accountTokens.length >= 2) {
    const shortAlias = new RegExp(`\\b${accountTokens[0]}\\s+${accountTokens.at(-1)}\\b`, 'i')
    const aliasIndex = normalized.search(shortAlias)
    if (aliasIndex >= 0) return { index: aliasIndex, score: 2 }
  }
  const tokenIndexes = accountTokens
    .filter((token) => token.length >= 3)
    .map((token) => normalized.search(new RegExp(`\\b${token}\\b`, 'i')))
    .filter((index) => index >= 0)
  return { index: tokenIndexes.length ? Math.min(...tokenIndexes) : -1, score: 1 }
}

function mentionedAccounts(input: string, accounts: LedgerAccount[]): LedgerAccount[] {
  const matches = accounts
    .map((account, order) => ({ account, order, ...accountMention(input, account) }))
    .filter((match) => match.index >= 0)
  return matches
    .filter((match) => !matches.some((other) => other.index === match.index && other.score > match.score))
    .sort((left, right) => left.index - right.index || right.score - left.score || left.order - right.order)
    .map((match) => match.account)
}

function inferMerchant(input: string, members: HouseholdMember[], amountMatch?: RegExpMatchArray | null): string {
  const cleaned = members.reduce((text, member) => text.replace(new RegExp(member.name.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'), 'gi'), ' '), input)
    .replace(amountMatch?.[0] ?? '', '')
    .replace(/\b(?:the\s+day\s+before\s+yesterday|today|yesterday|\d+\s+days?\s+ago|last\s+(?:night|week|month))\b/gi, ' ')
    .replace(/\b(paid|spent|received|got|for|from|using|via|split|equally|half|with|rs|rupees?)\b/gi, ' ')
    .replace(/\s+/g, ' ')
    .trim()

  const beforeAccount = cleaned.split(/hdfc|icici|cash/i)[0]?.trim()
  return beforeAccount ? beforeAccount.replace(/^[,\s]+|[,\s]+$/g, '') : ''
}

export function parseCaptureLocally(input: string, members: HouseholdMember[] = [], accounts: LedgerAccount[] = DEMO_ACCOUNTS): TransactionDraft {
  const amountMatch = input.match(/(?:₹|rs\.?\s*)?([\d,]+(?:\.\d{1,2})?)\s*(k|thousand|l|lac|lakh|cr|crore)?\b/i)
  const hasNegativeAmount = /(?:₹|rs\.?\s*)?-\s*[\d,]+(?:\.\d{1,2})?/i.test(input)
  const amountRupees = hasNegativeAmount ? 0 : amountInRupees(amountMatch, input)
  const transfer = /\b(?:self\s+)?tr(?:a)?nsfer\b|->|→|\bmove(?:d)?\b.*\bfrom\b.*\bto\b|\bwithdr(?:aw|ew|awn)\b|\bcredit\s+card\s+bill\b/i.test(input)
  const kind = transfer ? 'transfer' : /received|salary|income|credited|got paid/i.test(input) ? 'credit' : 'debit'
  const category = transfer ? 'Transfer' : CATEGORY_RULES.find(([pattern]) => pattern.test(input))?.[1] ?? 'Other'
  const matches = mentionedAccounts(input, accounts)
  const sourceAccount = matches[0] ?? accounts[0] ?? DEMO_ACCOUNTS[0]
  const destinationAccount = transfer ? matches.find((account) => account.id !== sourceAccount.id || account.name !== sourceAccount.name) : undefined
  const namedMembers = members.filter((member) => input.toLowerCase().includes(member.name.toLowerCase()))
  const wantsSplit = !transfer && /split|half|equal|50\s*\/\s*50|shared/i.test(input)
  const unknownNamedSplit = wantsSplit && /\bwith\b/i.test(input) && namedMembers.length === 0
  const selectedMembers = namedMembers.length ? namedMembers : wantsSplit && !unknownNamedSplit ? members : []
  const amountPaise = rupeesToPaise(amountRupees)
  const equalSharePaise = selectedMembers.length ? Math.floor(amountPaise / (selectedMembers.length + 1)) : 0

  return {
    kind,
    amountPaise,
    merchant: transfer ? 'Self transfer' : inferMerchant(input, members, amountMatch),
    category,
    account: sourceAccount.name,
    sourceAccountId: sourceAccount.id,
    destinationAccount: destinationAccount?.name,
    destinationAccountId: destinationAccount?.id,
    occurredAt: parseLocalDatePhrase(input),
    note: '',
    memberSplits: selectedMembers.map((member) => ({ memberId: member.id, memberName: member.name, amountPaise: equalSharePaise })),
    confidence: amountPaise > 0 && matches.length > 0 && category !== 'Other' && !unknownNamedSplit && (!transfer || Boolean(destinationAccount)) ? 'high' : 'review',
    sourceText: input
  }
}
