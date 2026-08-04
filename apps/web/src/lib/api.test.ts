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
})
