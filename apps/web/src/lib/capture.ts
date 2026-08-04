import type { HouseholdMember, TransactionDraft } from '../types'
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

const ACCOUNTS = ['HDFC UPI', 'ICICI Bank', 'Cash', 'HDFC Card']

function inferMerchant(input: string, members: HouseholdMember[], amountMatch?: RegExpMatchArray | null): string {
  const cleaned = members.reduce((text, member) => text.replace(new RegExp(member.name.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'), 'gi'), ' '), input)
    .replace(amountMatch?.[0] ?? '', '')
    .replace(/\b(paid|spent|received|got|for|from|using|via|split|equally|half|with|rs|rupees?)\b/gi, ' ')
    .replace(/\s+/g, ' ')
    .trim()

  const beforeAccount = cleaned.split(/hdfc|icici|cash/i)[0]?.trim()
  return beforeAccount ? beforeAccount.replace(/^[,\s]+|[,\s]+$/g, '') : 'New transaction'
}

export function parseCaptureLocally(input: string, members: HouseholdMember[] = []): TransactionDraft {
  const amountMatch = input.match(/(?:₹|rs\.?\s*)?([\d,]+(?:\.\d{1,2})?)/i)
  const amountRupees = amountMatch ? Number(amountMatch[1].replaceAll(',', '')) : 0
  const kind = /received|salary|income|credited|got paid/i.test(input) ? 'credit' : 'debit'
  const category = CATEGORY_RULES.find(([pattern]) => pattern.test(input))?.[1] ?? 'Other'
  const account = ACCOUNTS.find((candidate) => input.toLowerCase().includes(candidate.toLowerCase())) ?? 'HDFC UPI'
  const namedMembers = members.filter((member) => input.toLowerCase().includes(member.name.toLowerCase()))
  const wantsSplit = /split|half|equal|50\s*\/\s*50|shared/i.test(input)
  const selectedMembers = namedMembers.length ? namedMembers : wantsSplit ? members : []
  const amountPaise = rupeesToPaise(amountRupees)
  const equalSharePaise = selectedMembers.length ? Math.floor(amountPaise / (selectedMembers.length + 1)) : 0

  return {
    kind,
    amountPaise,
    merchant: inferMerchant(input, members, amountMatch),
    category,
    account,
    occurredAt: parseLocalDatePhrase(input),
    note: '',
    memberSplits: selectedMembers.map((member) => ({ memberId: member.id, memberName: member.name, amountPaise: equalSharePaise })),
    confidence: amountPaise > 0 && category !== 'Other' ? 'high' : 'review',
    sourceText: input
  }
}
