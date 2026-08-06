export type Paise = number
export type EntityId = string | number

export type SetupAccountKind = 'bank' | 'cash' | 'wallet' | 'credit_card'

export interface AccountSetupInput {
  name: string
  kind: SetupAccountKind
  opening_balance_paise: Paise
  credit_limit_paise: Paise | null
  statement_day: number | null
  payment_due_day: number | null
}

export interface LedgerAccount {
  id?: EntityId
  name: string
  kind: SetupAccountKind
}

export interface UserProfile {
  displayName: string
  householdName: string
  members: HouseholdMember[]
}

export interface HouseholdMember {
  id: string
  name: string
}

export interface MemberBalance extends HouseholdMember {
  balancePaise: Paise
  status: string
}

export interface TransactionSplit {
  memberId: string
  memberName: string
  amountPaise: Paise
}

export type TransactionKind = 'debit' | 'credit' | 'transfer'

export interface Transaction {
  id: string
  kind: TransactionKind
  amountPaise: Paise
  personalSharePaise: Paise
  merchant: string
  category: string
  account: string
  sourceAccountId?: EntityId
  destinationAccount?: string
  destinationAccountId?: EntityId
  occurredAt: string
  note?: string
  memberSplits: TransactionSplit[]
  status: 'confirmed'
}

export interface TransactionDraft {
  kind: TransactionKind
  amountPaise: Paise
  merchant: string
  category: string
  account: string
  sourceAccountId?: EntityId
  destinationAccount?: string
  destinationAccountId?: EntityId
  occurredAt: string
  note: string
  memberSplits: TransactionSplit[]
  confidence: 'high' | 'review'
  warnings?: string[]
  sourceText: string
}

export interface MonthlyPoint {
  month: string
  incomePaise: Paise
  spendPaise: Paise
}

export interface Dashboard {
  availablePaise: Paise
  incomePaise: Paise
  spendPaise: Paise
  sharedBalancePaise: Paise
  memberBalances: MemberBalance[]
  monthly: MonthlyPoint[]
  recentTransactions: Transaction[]
}

export type AssistantWidget =
  | { type: 'metric'; title: string; value: string; detail?: string }
  | { type: 'bar_chart' | 'line_chart'; title: string; data: Array<{ label: string; value: number }> }
  | { type: 'table'; title: string; columns: string[]; rows: string[][] }
  | { type: 'clarification'; question: string; options: string[] }

export interface AssistantReply {
  message: string
  widgets: AssistantWidget[]
  provider: string
}
