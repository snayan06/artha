import { demoDashboard, demoTransactions } from '../data/demo'
import type { AccountSetupInput, AssistantReply, AssistantWidget, Dashboard, HouseholdMember, LedgerAccount, MemberBalance, MonthlyPoint, Transaction, TransactionDraft, UserProfile } from '../types'
import { parseCaptureLocally } from './capture'

const API_URL = (import.meta.env.VITE_API_URL as string | undefined)?.replace(/\/$/, '')
const DEMO_MODE = import.meta.env.VITE_DEMO_MODE !== 'false'
const TIMEOUT_MS = 10_000
const RETRY_DELAY_MS = 250
const TRANSIENT_STATUSES = new Set([502, 503, 504])
const RETRYABLE_POST_PATHS = new Set([
  '/api/v1/drafts/parse',
  '/api/v1/assistant/chat'
])

type AccessTokenProvider = () => Promise<string | null>
let accessTokenProvider: AccessTokenProvider = async () => null

export function configureApiAccessTokenProvider(provider: AccessTokenProvider): void {
  accessTokenProvider = provider
}

type JsonObject = Record<string, unknown>

export type RecoveryBundle = JsonObject

export interface RecoverySummary {
  sha256: string
  householdName: string
  eligible: boolean
  blocker: string | null
  counts: {
    members: number
    accounts: number
    categories: number
    transactions: number
    splits: number
    transfers: number
    settlements: number
    merchantRules: number
    auditEvents: number
  }
}

export interface RecoveryRestoreResult {
  householdId: string
  restored: boolean
  idempotentReplay: boolean
  sha256: string
}

export class ApiError extends Error {
  constructor(readonly status: number, message: string) {
    super(message)
  }
}

export class CaptureDraftUnavailableError extends Error {
  readonly sourceText: string

  constructor(sourceText: string, options?: ErrorOptions) {
    super('Automatic interpretation is temporarily unavailable.', options)
    this.name = 'CaptureDraftUnavailableError'
    this.sourceText = sourceText
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  if (!API_URL) throw new Error('Demo mode')
  const accessToken = await accessTokenProvider()
  const headers: Record<string, string> = { 'Content-Type': 'application/json', ...(init?.headers as Record<string, string> | undefined) }
  if (accessToken) headers.Authorization = `Bearer ${accessToken}`
  const method = (init?.method ?? 'GET').toUpperCase()
  const canRetry = method === 'GET' || method === 'HEAD' || Boolean(headers['Idempotency-Key']) || RETRYABLE_POST_PATHS.has(path)
  const attempts = canRetry ? 2 : 1

  for (let attempt = 0; attempt < attempts; attempt += 1) {
    const controller = new AbortController()
    const timer = window.setTimeout(() => controller.abort(), TIMEOUT_MS)
    try {
      const response = await fetch(`${API_URL}${path}`, {
        ...init,
        headers,
        signal: controller.signal
      })
      if (!response.ok) {
        if (attempt + 1 < attempts && TRANSIENT_STATUSES.has(response.status)) {
          await new Promise((resolve) => window.setTimeout(resolve, RETRY_DELAY_MS))
          continue
        }
        let detail = ''
        try {
          const body = await response.clone().json() as JsonObject
          detail = safeText(body.detail, '', 240)
        } catch {
          // Non-JSON provider errors use the stable fallback below.
        }
        throw new ApiError(response.status, detail || `API request failed (${response.status})`)
      }
      return await response.json() as T
    } catch (error) {
      const timedOut = error instanceof Error && error.name === 'AbortError'
      const networkFailure = error instanceof TypeError
      if (attempt + 1 < attempts && (timedOut || networkFailure)) {
        await new Promise((resolve) => window.setTimeout(resolve, RETRY_DELAY_MS))
        continue
      }
      if (timedOut) throw new ApiError(408, 'Artha took too long to respond. Please try again.')
      if (networkFailure) throw new ApiError(503, 'Artha could not reach the API. Check your connection and try again.')
      throw error
    } finally {
      window.clearTimeout(timer)
    }
  }

  throw new ApiError(503, 'Artha could not reach the API. Please try again.')
}

function numberValue(value: unknown, fallback = 0): number {
  return typeof value === 'number' && Number.isSafeInteger(value) ? value : fallback
}

function stringValue(value: unknown, fallback: string): string {
  return typeof value === 'string' && value ? value : fallback
}

function safeText(value: unknown, fallback = '', maxLength = 500): string {
  return typeof value === 'string' ? value.slice(0, maxLength) : fallback
}

function formatAssistantPaise(value: number): string {
  return new Intl.NumberFormat('en-IN', { style: 'currency', currency: 'INR', maximumFractionDigits: 2 }).format(value / 100)
}

function mapAssistantWidgets(raw: unknown): AssistantWidget[] {
  if (!Array.isArray(raw)) return []
  return raw.slice(0, 8).flatMap<AssistantWidget>((item) => {
    if (!item || typeof item !== 'object') return []
    const widget = item as JsonObject
    const rawType = safeText(widget.type)
    if (rawType === 'metric') {
      const metricValue = typeof widget.value_paise === 'number' ? formatAssistantPaise(widget.value_paise) : safeText(widget.value, '—', 80)
      return [{ type: 'metric' as const, title: safeText(widget.title ?? widget.label, 'Metric', 80), value: metricValue, detail: safeText(widget.caption ?? widget.detail ?? widget.subtitle, '', 160) || undefined }]
    }
    if (rawType === 'chart' || rawType === 'bar' || rawType === 'bar_chart' || rawType === 'line' || rawType === 'line_chart') {
      const dataRaw = Array.isArray(widget.points) ? widget.points : Array.isArray(widget.data) ? widget.data : []
      const data = dataRaw.slice(0, 24).flatMap((point) => {
        if (!point || typeof point !== 'object') return []
        const row = point as JsonObject
        const value = typeof row.value_paise === 'number' ? row.value_paise / 100 : row.value
        return typeof value === 'number' && Number.isFinite(value) ? [{ label: safeText(row.label ?? row.name, 'Item', 50), value }] : []
      })
      if (!data.length) return []
      const chartKind = safeText(widget.chart_type, rawType)
      return [{ type: chartKind.startsWith('line') ? 'line_chart' as const : 'bar_chart' as const, title: safeText(widget.title, 'Chart', 80), data }]
    }
    if (rawType === 'table') {
      const rawRows = (Array.isArray(widget.rows) ? widget.rows : []).slice(0, 30)
      const hasStructuredRows = rawRows.some((row) => row && typeof row === 'object' && !Array.isArray(row))
      const columns = hasStructuredRows ? ['Item', 'Amount', 'Date'] : (Array.isArray(widget.columns) ? widget.columns : []).slice(0, 8).map((column) => safeText(column, 'Column', 60))
      const rows = rawRows.flatMap((row) => {
        if (Array.isArray(row)) return [row.slice(0, columns.length || 8).map((cell) => safeText(String(cell), '', 120))]
        if (!row || typeof row !== 'object') return []
        const structured = row as JsonObject
        return [[safeText(structured.label, 'Item', 80), typeof structured.amount_paise === 'number' ? formatAssistantPaise(structured.amount_paise) : '—', safeText(structured.date, '—', 10)]]
      })
      if (!columns.length || !rows.length) return []
      return [{ type: 'table' as const, title: safeText(widget.title, 'Details', 80), columns, rows }]
    }
    if (rawType === 'insight') {
      const body = safeText(widget.body ?? widget.text, '', 800)
      return body ? [{ type: 'insight' as const, title: safeText(widget.title, 'Insight', 80), body }] : []
    }
    if (rawType === 'clarification') {
      const question = safeText(widget.question ?? widget.text, '', 300)
      const optionSource = Array.isArray(widget.choices) ? widget.choices : Array.isArray(widget.options) ? widget.options : []
      const options = optionSource.slice(0, 6).map((option) => safeText(option, '', 100)).filter(Boolean)
      return question ? [{ type: 'clarification' as const, question, options }] : []
    }
    return []
  })
}

function entityId(value: unknown): string | number | undefined {
  if (typeof value === 'string' && value) return value
  if (typeof value === 'number' && Number.isSafeInteger(value)) return value
  return undefined
}

function apiEntityId(value: string): string | number {
  return /^\d+$/.test(value) ? Number(value) : value
}

function mapSplits(raw: unknown, memberNames: Map<string, string>): Transaction['memberSplits'] {
  if (!Array.isArray(raw)) return []
  return raw.flatMap((item) => {
    const split = item as JsonObject
    const rawMemberId = entityId(split.member_id)
    if (rawMemberId === undefined) return []
    const memberId = String(rawMemberId)
    return [{ memberId, memberName: memberNames.get(memberId) ?? 'Household member', amountPaise: numberValue(split.amount_paise) }]
  })
}

function mapTransaction(raw: JsonObject, accountNames: Map<string, string> = new Map(), memberNames: Map<string, string> = new Map()): Transaction {
  const apiKind = stringValue(raw.kind, 'expense')
  const amountPaise = numberValue(raw.amount_paise ?? raw.amountPaise)
  const memberSplits = mapSplits(raw.splits, memberNames)
  const memberTotalPaise = memberSplits.reduce((sum, split) => sum + split.amountPaise, 0)
  return {
    id: typeof raw.id === 'number' ? String(raw.id) : stringValue(raw.id, crypto.randomUUID()),
    kind: apiKind === 'transfer' ? 'transfer' : apiKind === 'income' || apiKind === 'credit' ? 'credit' : 'debit',
    amountPaise,
    personalSharePaise: numberValue(raw.personal_share_paise ?? raw.personalSharePaise, amountPaise - memberTotalPaise),
    merchant: stringValue(raw.description ?? raw.merchant, 'Transaction'),
    category: stringValue(raw.category, 'Other'),
    account: stringValue(raw.account_name ?? raw.account, accountNames.get(String(entityId(raw.source_account_id) ?? '')) ?? (raw.source_account_id ? 'Primary account' : 'Account')),
    sourceAccountId: entityId(raw.source_account_id),
    destinationAccount: stringValue(raw.destination_account_name, accountNames.get(String(entityId(raw.destination_account_id) ?? '')) ?? '') || undefined,
    destinationAccountId: entityId(raw.destination_account_id),
    occurredAt: stringValue(raw.occurred_at ?? raw.occurredAt, new Date().toISOString()).slice(0, 10),
    note: typeof (raw.notes ?? raw.note) === 'string' ? String(raw.notes ?? raw.note) : undefined,
    memberSplits,
    status: 'confirmed'
  }
}

function mapDraft(raw: JsonObject, text: string, memberNames: Map<string, string>, confidence?: unknown, warnings?: unknown): TransactionDraft {
  const amountPaise = numberValue(raw.amount_paise ?? raw.amountPaise)
  const apiKind = stringValue(raw.kind, 'expense')
  const warningList = Array.isArray(warnings)
    ? warnings.slice(0, 5).map((warning) => safeText(warning, '', 160)).filter(Boolean)
    : []
  return {
    kind: apiKind === 'transfer' ? 'transfer' : apiKind === 'income' || apiKind === 'credit' ? 'credit' : 'debit',
    amountPaise,
    merchant: stringValue(raw.description ?? raw.merchant, 'New transaction'),
    category: stringValue(raw.category, 'Other'),
    account: stringValue(raw.account_name ?? raw.account, 'HDFC UPI'),
    sourceAccountId: entityId(raw.source_account_id),
    destinationAccount: stringValue(raw.destination_account_name, '') || undefined,
    destinationAccountId: entityId(raw.destination_account_id),
    occurredAt: stringValue(raw.occurred_at ?? raw.occurredAt, new Date().toISOString()).slice(0, 10),
    note: stringValue(raw.notes ?? raw.note, ''),
    memberSplits: mapSplits(raw.splits, memberNames),
    confidence: warningList.length === 0 && (confidence === 'high' || (typeof confidence === 'number' && confidence >= 0.8)) ? 'high' : 'review',
    warnings: warningList,
    sourceText: text
  }
}

function toApiDraft(draft: TransactionDraft): JsonObject {
  const memberTotalPaise = draft.memberSplits.reduce((sum, split) => sum + split.amountPaise, 0)
  return {
    kind: draft.kind === 'transfer' ? 'transfer' : draft.kind === 'credit' ? 'income' : 'expense',
    amount_paise: draft.amountPaise,
    description: draft.merchant,
    category: draft.category,
    paid_by_member_id: null,
    personal_share_paise: draft.amountPaise - memberTotalPaise,
    splits: draft.memberSplits.map((split) => ({ member_id: apiEntityId(split.memberId), amount_paise: split.amountPaise })),
    occurred_at: `${draft.occurredAt}T12:00:00Z`,
    notes: draft.note || null,
    source_account_id: draft.sourceAccountId,
    destination_account_id: draft.destinationAccountId ?? null
  }
}

function accountNameMap(raw: unknown): Map<string, string> {
  const rows = Array.isArray(raw) ? raw : []
  return new Map(rows.flatMap((item) => {
    const account = item as JsonObject
    const id = entityId(account.id)
    return id !== undefined ? [[String(id), stringValue(account.name, 'Account')] as const] : []
  }))
}

function memberNameMap(raw: unknown): Map<string, string> {
  const rows = Array.isArray(raw) ? raw : []
  return new Map(rows.flatMap((item) => {
    const member = item as JsonObject
    const id = member.id ?? member.member_id
    const normalizedId = entityId(id)
    return normalizedId !== undefined ? [[String(normalizedId), stringValue(member.name ?? member.member_name, 'Household member')] as const] : []
  }))
}

function mapMembers(raw: unknown): HouseholdMember[] {
  return [...memberNameMap(raw)].map(([id, name]) => ({ id: String(id), name }))
}

function monthlyFromTransactions(rows: JsonObject[]): MonthlyPoint[] {
  const monthFormat = new Intl.DateTimeFormat('en-IN', { month: 'short' })
  const now = new Date()
  return Array.from({ length: 6 }, (_, index) => {
    const date = new Date(now.getFullYear(), now.getMonth() - 5 + index, 1)
    const key = `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}`
    const matching = rows.filter((row) => stringValue(row.occurred_at, '').startsWith(key))
    return {
      month: monthFormat.format(date),
      incomePaise: matching.filter((row) => row.kind === 'income').reduce((sum, row) => sum + numberValue(row.personal_share_paise), 0),
      spendPaise: matching.filter((row) => row.kind === 'expense').reduce((sum, row) => sum + numberValue(row.personal_share_paise), 0)
    }
  })
}

export async function bootstrapDemo(): Promise<void> {
  if (!API_URL) return
  await request('/api/v1/demo/bootstrap', { method: 'POST' })
}

export async function setupOnboarding(accounts: AccountSetupInput[], members: Array<{ name: string }>, displayName = 'You', householdName = 'My household'): Promise<HouseholdMember[]> {
  const response = await request<JsonObject>('/api/v1/onboarding/setup', {
    method: 'POST',
    body: JSON.stringify({ accounts, members, display_name: displayName, household_name: householdName })
  })
  return mapMembers(response.members)
}

export async function isOnboardingComplete(): Promise<boolean> {
  if (DEMO_MODE) return true
  try {
    await request<unknown>('/api/v1/accounts')
    return true
  } catch (error) {
    if (error instanceof ApiError && error.status === 409) return false
    throw error
  }
}

export async function getMembers(): Promise<HouseholdMember[]> {
  return mapMembers(await request<unknown>('/api/v1/members'))
}

export async function getUserProfile(): Promise<UserProfile> {
  const raw = await request<JsonObject>('/api/v1/profile')
  return {
    displayName: stringValue(raw.display_name, 'You'),
    householdName: stringValue(raw.household_name, 'My household'),
    members: mapMembers(raw.members)
  }
}

function mapRecoverySummary(raw: JsonObject): RecoverySummary {
  return {
    sha256: stringValue(raw.sha256, ''),
    householdName: stringValue(raw.household_name, 'Restored household'),
    eligible: raw.eligible === true,
    blocker: typeof raw.blocker === 'string' ? safeText(raw.blocker, '', 240) : null,
    counts: {
      members: numberValue(raw.members),
      accounts: numberValue(raw.accounts),
      categories: numberValue(raw.categories),
      transactions: numberValue(raw.transactions),
      splits: numberValue(raw.splits),
      transfers: numberValue(raw.transfers),
      settlements: numberValue(raw.settlements),
      merchantRules: numberValue(raw.merchant_rules),
      auditEvents: numberValue(raw.audit_events)
    }
  }
}

export async function getRecoveryExport(): Promise<RecoveryBundle> {
  const bundle = await request<unknown>('/api/v1/recovery/export')
  if (!bundle || typeof bundle !== 'object' || Array.isArray(bundle)) throw new Error('Artha returned an invalid recovery bundle.')
  return bundle as RecoveryBundle
}

export async function previewRecoveryBundle(bundle: RecoveryBundle): Promise<RecoverySummary> {
  const response = await request<JsonObject>('/api/v1/recovery/preview', {
    method: 'POST',
    body: JSON.stringify(bundle)
  })
  return mapRecoverySummary(response)
}

export async function restoreRecoveryBundle(bundle: RecoveryBundle, idempotencyKey: string = crypto.randomUUID()): Promise<RecoveryRestoreResult> {
  const response = await request<JsonObject>('/api/v1/recovery/restore', {
    method: 'POST',
    headers: { 'Idempotency-Key': idempotencyKey },
    body: JSON.stringify(bundle)
  })
  return {
    householdId: stringValue(response.household_id, ''),
    restored: response.restored === true,
    idempotentReplay: response.idempotent_replay === true,
    sha256: stringValue(response.sha256, '')
  }
}

export async function getAccounts(): Promise<LedgerAccount[]> {
  try {
    const raw = await request<unknown>('/api/v1/accounts')
    const rows = Array.isArray(raw) ? raw : Array.isArray((raw as JsonObject)?.items) ? (raw as JsonObject).items as unknown[] : []
    return rows.flatMap((item) => {
      const account = item as JsonObject
      const id = entityId(account.id)
      if (!id) return []
      const rawKind = stringValue(account.kind ?? account.type, 'bank')
      const kind: LedgerAccount['kind'] = rawKind === 'cash' || rawKind === 'wallet' || rawKind === 'credit_card' ? rawKind : 'bank'
      return [{ id, name: stringValue(account.name, 'Account'), kind }]
    })
  } catch (error) {
    if (!DEMO_MODE) throw error
    return [
      { id: 'demo-hdfc-upi', name: 'HDFC UPI', kind: 'bank' },
      { id: 'demo-icici-bank', name: 'ICICI Bank', kind: 'bank' },
      { id: 'demo-hdfc-card', name: 'HDFC Card', kind: 'credit_card' }
    ]
  }
}

export async function chatAssistant(message: string): Promise<AssistantReply> {
  try {
    const response = await request<JsonObject>('/api/v1/assistant/chat', {
      method: 'POST',
      body: JSON.stringify({ message })
    })
    const result = response.result && typeof response.result === 'object' ? response.result as JsonObject : response
    const providerRaw = response.provider_status && typeof response.provider_status === 'object' ? response.provider_status as JsonObject : response
    const provider = safeText(providerRaw.provider ?? providerRaw.name ?? response.provider, 'Artha assistant', 80)
    const model = safeText(response.model, '', 80)
    const intent = safeText(result.intent, 'ledger', 40).replaceAll('_', ' ')
    return {
      message: safeText(response.message ?? response.answer ?? response.content, `Here is your ${intent} view.`, 2000),
      widgets: mapAssistantWidgets(result.widgets ?? response.widgets),
      provider: model ? `${provider} · ${model}` : provider,
      deterministicFallback: response.mode === 'deterministic_fallback' || response.deterministic_fallback === true || providerRaw.deterministic_fallback === true || providerRaw.status === 'fallback'
    }
  } catch (error) {
    if (!DEMO_MODE) throw error
    return {
      message: 'The AI provider is unavailable, so this is a deterministic preview using local demo totals.',
      provider: 'Deterministic local preview',
      deterministicFallback: true,
      widgets: [
        { type: 'metric', title: 'Available balance', value: `₹${(demoDashboard.availablePaise / 100).toLocaleString('en-IN')}`, detail: 'Demo data, not your live ledger' },
        { type: 'insight', title: 'Safe fallback', body: `Your demo spend is ₹${(demoDashboard.spendPaise / 100).toLocaleString('en-IN')}. Connect the API to ask questions about your own ledger.` }
      ]
    }
  }
}

export async function getDashboard(): Promise<{ data: Dashboard; demo: boolean }> {
  try {
    const raw = await request<JsonObject>('/api/v1/dashboard')
    const recentRaw = Array.isArray(raw.recent_transactions ?? raw.recentTransactions) ? (raw.recent_transactions ?? raw.recentTransactions) as JsonObject[] : []
    const names = accountNameMap(raw.accounts)
    const membersRaw = Array.isArray(raw.member_balances) ? raw.member_balances : []
    const memberNames = memberNameMap(membersRaw)
    const memberBalances: MemberBalance[] = membersRaw.map((item) => {
      const balance = item as JsonObject
      const id = String(entityId(balance.member_id) ?? '')
      return { id, name: stringValue(balance.member_name, memberNames.get(id) ?? 'Household member'), balancePaise: numberValue(balance.balance_paise), status: stringValue(balance.status, '') }
    })
    const monthlyRaw = Array.isArray(raw.monthly) ? raw.monthly : []
    const monthly: MonthlyPoint[] = monthlyRaw.map((item) => {
      const point = item as JsonObject
      return {
        month: stringValue(point.month, ''),
        incomePaise: numberValue(point.income_paise ?? point.incomePaise),
        spendPaise: numberValue(point.spend_paise ?? point.spendPaise)
      }
    })
    return {
      data: {
        availablePaise: numberValue(raw.total_balance_paise ?? raw.available_paise ?? raw.availablePaise),
        incomePaise: numberValue(raw.income_paise ?? raw.incomePaise),
        spendPaise: numberValue(raw.spend_paise ?? raw.spendPaise),
        sharedBalancePaise: memberBalances.reduce((sum, balance) => sum + balance.balancePaise, 0),
        memberBalances,
        monthly: monthly.length ? monthly : monthlyFromTransactions(recentRaw),
        recentTransactions: recentRaw.map((item) => mapTransaction(item, names, memberNames))
      },
      demo: false
    }
  } catch (error) {
    if (!DEMO_MODE) throw error
    return { data: demoDashboard, demo: true }
  }
}

export async function getTransactions(): Promise<{ data: Transaction[]; demo: boolean }> {
  try {
    const [raw, accounts, members] = await Promise.all([
      request<unknown>('/api/v1/transactions'),
      request<unknown>('/api/v1/accounts'),
      request<unknown>('/api/v1/members')
    ])
    const rows = Array.isArray(raw) ? raw : Array.isArray((raw as JsonObject)?.items) ? (raw as JsonObject).items as unknown[] : []
    const names = accountNameMap(accounts)
    const memberNames = memberNameMap(members)
    return { data: rows.map((item) => mapTransaction(item as JsonObject, names, memberNames)), demo: false }
  } catch (error) {
    if (!DEMO_MODE) throw error
    return { data: demoTransactions, demo: true }
  }
}

export async function parseDraft(text: string, membersForFallback: HouseholdMember[] = []): Promise<{ data: TransactionDraft; demo: boolean }> {
  try {
    const [response, accounts, members] = await Promise.all([
      request<JsonObject>('/api/v1/drafts/parse', {
        method: 'POST',
        body: JSON.stringify({ text, timezone: Intl.DateTimeFormat().resolvedOptions().timeZone })
      }),
      request<unknown>('/api/v1/accounts'),
      request<unknown>('/api/v1/members')
    ])
    const rawDraft = (response.draft ?? response) as JsonObject
    const memberNames = memberNameMap(members)
    const draft = mapDraft(rawDraft, text, memberNames, response.confidence, response.warnings)
    const names = accountNameMap(accounts)
    return {
      data: {
        ...draft,
        account: draft.sourceAccountId !== undefined ? names.get(String(draft.sourceAccountId)) ?? draft.account : draft.account
      },
      demo: false
    }
  } catch (error) {
    if (error instanceof ApiError && error.status >= 400 && error.status < 500) throw error
    if (DEMO_MODE) return { data: parseCaptureLocally(text, membersForFallback), demo: true }
    throw new CaptureDraftUnavailableError(text, { cause: error })
  }
}

export async function confirmDraft(draft: TransactionDraft, idempotencyKey: string = crypto.randomUUID()): Promise<Transaction> {
  try {
    const raw = await request<JsonObject>('/api/v1/transactions/confirm', {
      method: 'POST',
      headers: { 'Idempotency-Key': idempotencyKey },
      body: JSON.stringify(toApiDraft(draft))
    })
    return {
      ...mapTransaction(raw),
      account: draft.account,
      destinationAccount: draft.destinationAccount,
      destinationAccountId: draft.destinationAccountId,
      memberSplits: draft.memberSplits
    }
  } catch (error) {
    if (API_URL && (error instanceof ApiError || !DEMO_MODE)) throw error
    return {
      id: `demo-${Date.now()}`,
      kind: draft.kind,
      amountPaise: draft.amountPaise,
      personalSharePaise: draft.amountPaise - draft.memberSplits.reduce((sum, split) => sum + split.amountPaise, 0),
      merchant: draft.merchant,
      category: draft.category,
      account: draft.account,
      sourceAccountId: draft.sourceAccountId,
      destinationAccount: draft.destinationAccount,
      destinationAccountId: draft.destinationAccountId,
      occurredAt: draft.occurredAt,
      note: draft.note || undefined,
      memberSplits: draft.memberSplits,
      status: 'confirmed'
    }
  }
}
