import { afterEach, describe, expect, it, vi } from 'vitest'
import type { TransactionDraft } from '../types'

describe('FastAPI adapter', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
    vi.unstubAllEnvs()
    vi.resetModules()
  })

  it('preserves the parsed source account id through confirmation', async () => {
    vi.stubEnv('VITE_API_URL', 'http://api.test')
    vi.stubEnv('VITE_DEMO_MODE', 'true')
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(new Response(JSON.stringify({
        draft: {
          kind: 'expense', amount_paise: 184000, description: 'Groceries', category: 'Groceries',
          paid_by_member_id: null, personal_share_paise: 92000, splits: [{ member_id: 7, amount_paise: 92000 }],
          source_account_id: 42, occurred_at: '2026-08-04T12:00:00Z'
        }, confidence: 0.97, warnings: []
      }), { status: 200, headers: { 'Content-Type': 'application/json' } }))
      .mockResolvedValueOnce(new Response(JSON.stringify([
        { id: 42, name: 'HDFC UPI' }
      ]), { status: 200, headers: { 'Content-Type': 'application/json' } }))
      .mockResolvedValueOnce(new Response(JSON.stringify([
        { id: 7, name: 'Sam' }
      ]), { status: 200, headers: { 'Content-Type': 'application/json' } }))
      .mockResolvedValueOnce(new Response(JSON.stringify({
        id: 9, kind: 'expense', amount_paise: 184000, description: 'Groceries', category: 'Groceries',
        paid_by_member_id: null, personal_share_paise: 92000, splits: [{ member_id: 7, amount_paise: 92000 }],
        source_account_id: 42, occurred_at: '2026-08-04T12:00:00Z'
      }), { status: 200, headers: { 'Content-Type': 'application/json' } }))
    vi.stubGlobal('fetch', fetchMock)
    const { confirmDraft, parseDraft } = await import('./api')

    const parsed = await parseDraft('Paid 1840 for groceries from HDFC UPI, split equally with Sam')
    expect(JSON.parse(String((fetchMock.mock.calls[0]?.[1] as RequestInit).body))).toEqual(expect.objectContaining({ timezone: expect.any(String) }))
    expect(parsed.data.sourceAccountId).toBe(42)
    const confirmed = await confirmDraft(parsed.data)

    const confirmInit = fetchMock.mock.calls[3]?.[1] as RequestInit
    expect(JSON.parse(String(confirmInit.body))).toMatchObject({ source_account_id: 42, paid_by_member_id: null, splits: [{ member_id: 7, amount_paise: 92000 }] })
    expect((confirmInit.headers as Record<string, string>)['Idempotency-Key']).toBeTruthy()
    expect(confirmed.account).toBe('HDFC UPI')
    expect(parsed.data.memberSplits).toEqual([{ memberId: '7', memberName: 'Sam', amountPaise: 92000 }])
  })

  it('surfaces API validation errors instead of creating a fake success', async () => {
    vi.stubEnv('VITE_API_URL', 'http://api.test')
    vi.stubEnv('VITE_DEMO_MODE', 'true')
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response('{}', { status: 422 })))
    const { confirmDraft } = await import('./api')
    const draft: TransactionDraft = {
      kind: 'debit', amountPaise: 10000, merchant: 'Test', category: 'Other', account: 'HDFC UPI',
      sourceAccountId: 42, occurredAt: '2026-08-04', note: '', memberSplits: [],
      confidence: 'high', sourceText: 'Paid 100'
    }

    await expect(confirmDraft(draft)).rejects.toThrow('API request failed (422)')
  })

  it('does not hide a parser validation error behind the local fallback', async () => {
    vi.stubEnv('VITE_API_URL', 'http://api.test')
    vi.stubEnv('VITE_DEMO_MODE', 'true')
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response('{}', { status: 422 })))
    const { parseDraft } = await import('./api')

    await expect(parseDraft('split equally without an amount')).rejects.toThrow('API request failed (422)')
  })

  it('uses the local parser only for a transient API outage in demo mode', async () => {
    vi.stubEnv('VITE_API_URL', 'http://api.test')
    vi.stubEnv('VITE_DEMO_MODE', 'true')
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response('{}', { status: 503 })))
    const { parseDraft } = await import('./api')

    const parsed = await parseDraft('Paid 250 for coffee yesterday from HDFC UPI')
    expect(parsed.demo).toBe(true)
    expect(parsed.data.amountPaise).toBe(25_000)
    expect(parsed.data.occurredAt).toMatch(/^\d{4}-\d{2}-\d{2}$/)
  })

  it('never substitutes fictional ledger data during a production API outage', async () => {
    vi.stubEnv('VITE_API_URL', 'https://api.artha.test')
    vi.stubEnv('VITE_DEMO_MODE', 'false')
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response('{}', { status: 503 })))
    const { chatAssistant, getAccounts, getDashboard, getTransactions } = await import('./api')

    await expect(getDashboard()).rejects.toThrow('API request failed (503)')
    await expect(getTransactions()).rejects.toThrow('API request failed (503)')
    await expect(getAccounts()).rejects.toThrow('API request failed (503)')
    await expect(chatAssistant('What is my balance?')).rejects.toThrow('API request failed (503)')
  })

  it('derives production onboarding state from the authenticated household', async () => {
    vi.stubEnv('VITE_API_URL', 'https://api.artha.test')
    vi.stubEnv('VITE_DEMO_MODE', 'false')
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(new Response('[]', { status: 200, headers: { 'Content-Type': 'application/json' } }))
      .mockResolvedValueOnce(new Response('{}', { status: 409 }))
    vi.stubGlobal('fetch', fetchMock)
    const { isOnboardingComplete } = await import('./api')

    await expect(isOnboardingComplete()).resolves.toBe(true)
    await expect(isOnboardingComplete()).resolves.toBe(false)
  })

  it('bootstraps the API in demo mode', async () => {
    vi.stubEnv('VITE_API_URL', 'http://api.test')
    vi.stubEnv('VITE_DEMO_MODE', 'true')
    const fetchMock = vi.fn().mockResolvedValue(new Response('{}', { status: 200 }))
    vi.stubGlobal('fetch', fetchMock)
    const { bootstrapDemo } = await import('./api')

    await bootstrapDemo()
    expect(fetchMock).toHaveBeenCalledWith('http://api.test/api/v1/demo/bootstrap', expect.objectContaining({ method: 'POST' }))
  })

  it('injects the current bearer token into FastAPI requests', async () => {
    vi.stubEnv('VITE_API_URL', 'http://api.test')
    const fetchMock = vi.fn().mockResolvedValue(new Response('[]', { status: 200, headers: { 'Content-Type': 'application/json' } }))
    vi.stubGlobal('fetch', fetchMock)
    const { configureApiAccessTokenProvider, getMembers } = await import('./api')
    configureApiAccessTokenProvider(async () => 'current-access-token')

    await getMembers()

    const request = fetchMock.mock.calls[0]?.[1] as RequestInit
    expect(request.headers).toEqual(expect.objectContaining({ Authorization: 'Bearer current-access-token' }))
  })

  it('hydrates the returning user profile from the server', async () => {
    vi.stubEnv('VITE_API_URL', 'https://api.artha.test')
    vi.stubEnv('VITE_DEMO_MODE', 'false')
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(JSON.stringify({
      display_name: 'Ari',
      household_name: 'Ari household',
      members: [{ id: 'member-1', name: 'Sam' }]
    }), { status: 200, headers: { 'Content-Type': 'application/json' } })))
    const { getUserProfile } = await import('./api')

    await expect(getUserProfile()).resolves.toEqual({
      displayName: 'Ari',
      householdName: 'Ari household',
      members: [{ id: 'member-1', name: 'Sam' }]
    })
  })

  it('retries a transient first GET without requiring the user to try again', async () => {
    vi.stubEnv('VITE_API_URL', 'https://api.artha.test')
    vi.stubEnv('VITE_DEMO_MODE', 'false')
    const fetchMock = vi.fn()
      .mockRejectedValueOnce(new TypeError('Failed to fetch'))
      .mockResolvedValueOnce(new Response(JSON.stringify([{ id: 42, name: 'HDFC UPI', type: 'bank' }]), {
        status: 200,
        headers: { 'Content-Type': 'application/json' }
      }))
    vi.stubGlobal('fetch', fetchMock)
    const { getAccounts } = await import('./api')

    await expect(getAccounts()).resolves.toEqual([{ id: 42, name: 'HDFC UPI', kind: 'bank' }])
    expect(fetchMock).toHaveBeenCalledTimes(2)
  })

  it('does not retry a non-idempotent setup write', async () => {
    vi.stubEnv('VITE_API_URL', 'https://api.artha.test')
    vi.stubEnv('VITE_DEMO_MODE', 'false')
    const fetchMock = vi.fn().mockRejectedValue(new TypeError('Failed to fetch'))
    vi.stubGlobal('fetch', fetchMock)
    const { setupOnboarding } = await import('./api')

    await expect(setupOnboarding([], [])).rejects.toThrow('Artha could not reach the API')
    expect(fetchMock).toHaveBeenCalledTimes(1)
  })

  it('retries a confirmed write with the same idempotency key', async () => {
    vi.stubEnv('VITE_API_URL', 'https://api.artha.test')
    vi.stubEnv('VITE_DEMO_MODE', 'false')
    const fetchMock = vi.fn()
      .mockRejectedValueOnce(new TypeError('Failed to fetch'))
      .mockResolvedValueOnce(new Response(JSON.stringify({
        id: 9, kind: 'expense', amount_paise: 10_000, personal_share_paise: 10_000,
        description: 'Coffee', category: 'Dining', source_account_id: 42,
        occurred_at: '2026-08-04T12:00:00Z', splits: []
      }), { status: 200, headers: { 'Content-Type': 'application/json' } }))
    vi.stubGlobal('fetch', fetchMock)
    const { confirmDraft } = await import('./api')
    const draft: TransactionDraft = {
      kind: 'debit', amountPaise: 10_000, merchant: 'Coffee', category: 'Dining', account: 'HDFC UPI',
      sourceAccountId: 42, occurredAt: '2026-08-04', note: '', memberSplits: [],
      confidence: 'high', sourceText: 'Paid 100 for coffee'
    }

    await expect(confirmDraft(draft)).resolves.toMatchObject({ id: '9', amountPaise: 10_000 })
    expect(fetchMock).toHaveBeenCalledTimes(2)
    const firstHeaders = (fetchMock.mock.calls[0]?.[1] as RequestInit).headers as Record<string, string>
    const secondHeaders = (fetchMock.mock.calls[1]?.[1] as RequestInit).headers as Record<string, string>
    expect(firstHeaders['Idempotency-Key']).toBeTruthy()
    expect(secondHeaders['Idempotency-Key']).toBe(firstHeaders['Idempotency-Key'])
  })

  it('posts reviewed setup accounts with card metadata', async () => {
    vi.stubEnv('VITE_API_URL', 'http://api.test')
    const fetchMock = vi.fn().mockResolvedValue(new Response('[]', { status: 200, headers: { 'Content-Type': 'application/json' } }))
    vi.stubGlobal('fetch', fetchMock)
    const { setupOnboarding } = await import('./api')
    const accounts = [{
      name: 'Travel Card', kind: 'credit_card' as const, opening_balance_paise: -12_500,
      credit_limit_paise: 200_000, statement_day: 5, payment_due_day: 25
    }]

    fetchMock.mockResolvedValueOnce(new Response(JSON.stringify({ accounts: [], members: [{ id: 7, name: 'Sam' }] }), { status: 200, headers: { 'Content-Type': 'application/json' } }))
    await setupOnboarding(accounts, [{ name: 'Sam' }])
    const request = fetchMock.mock.calls[0]?.[1] as RequestInit
    expect(JSON.parse(String(request.body))).toEqual({
      accounts,
      members: [{ name: 'Sam' }],
      display_name: 'You',
      household_name: 'My household'
    })
  })

  it('maps only approved assistant widgets from the strict API response', async () => {
    vi.stubEnv('VITE_API_URL', 'http://api.test')
    const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify({
      provider: 'disabled', model: null, mode: 'deterministic_fallback',
      result: { intent: 'spending', widgets: [
        { type: 'metric', title: 'Spend', value_paise: 12345, caption: 'This month', tone: 'neutral' },
        { type: 'chart', title: 'Trend', chart_type: 'line', points: [{ label: 'Aug', value_paise: 5000 }] },
        { type: 'clarification', question: 'Which period?', choices: ['This month'] },
        { type: 'html', content: '<img src=x onerror=alert(1)>' }
      ] }
    }), { status: 200, headers: { 'Content-Type': 'application/json' } }))
    vi.stubGlobal('fetch', fetchMock)
    const { chatAssistant } = await import('./api')

    const reply = await chatAssistant('Show spending')
    expect(JSON.parse(String((fetchMock.mock.calls[0]?.[1] as RequestInit).body))).toEqual({ message: 'Show spending' })
    expect(reply.deterministicFallback).toBe(true)
    expect(reply.widgets.map((widget) => widget.type)).toEqual(['metric', 'line_chart', 'clarification'])
    expect(JSON.stringify(reply)).not.toContain('onerror')
  })

  it('previews and restores a recovery bundle with an idempotency key', async () => {
    vi.stubEnv('VITE_API_URL', 'https://api.artha.test')
    vi.stubEnv('VITE_DEMO_MODE', 'false')
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(new Response(JSON.stringify({
        sha256: 'a'.repeat(64), household_name: 'Family ledger', eligible: true, blocker: null,
        members: 2, accounts: 4, categories: 8, transactions: 42, splits: 10,
        transfers: 3, settlements: 1, merchant_rules: 2, audit_events: 20
      }), { status: 200, headers: { 'Content-Type': 'application/json' } }))
      .mockResolvedValueOnce(new Response(JSON.stringify({
        household_id: 'household-1', restored: true, idempotent_replay: false, sha256: 'a'.repeat(64)
      }), { status: 201, headers: { 'Content-Type': 'application/json' } }))
    vi.stubGlobal('fetch', fetchMock)
    const { previewRecoveryBundle, restoreRecoveryBundle } = await import('./api')
    const bundle = { format: 'artha-recovery', schema_version: 1 }

    await expect(previewRecoveryBundle(bundle)).resolves.toMatchObject({ householdName: 'Family ledger', eligible: true, counts: { accounts: 4, transactions: 42 } })
    await expect(restoreRecoveryBundle(bundle, 'restore-key-123')).resolves.toMatchObject({ householdId: 'household-1', restored: true })

    const restoreRequest = fetchMock.mock.calls[1]?.[1] as RequestInit
    expect(restoreRequest.method).toBe('POST')
    expect(restoreRequest.headers).toEqual(expect.objectContaining({ 'Idempotency-Key': 'restore-key-123' }))
    expect(JSON.parse(String(restoreRequest.body))).toEqual(bundle)
  })
})
