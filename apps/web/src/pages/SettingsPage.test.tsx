import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import * as api from '../lib/api'
import { RouterProvider } from '../lib/router'
import { SettingsPage } from './SettingsPage'

describe('SettingsPage', () => {
  afterEach(() => {
    cleanup()
    vi.restoreAllMocks()
    vi.unstubAllEnvs()
  })

  it('keeps the server-owned private-data policy in a compact disclosure', async () => {
    vi.stubEnv('VITE_DEMO_MODE', 'false')
    vi.spyOn(api, 'getManagedAccounts').mockResolvedValue([])
    vi.spyOn(api, 'getAssistantStatus').mockResolvedValue({
      configured: true,
      provider: 'gemini',
      model: 'gemini-3.5-flash-lite',
      available: true,
      dataPolicy: 'private_approved',
      personalDataEnabled: true,
      isDemo: false
    })
    render(<RouterProvider><SettingsPage /></RouterProvider>)

    const summary = screen.getByText('Privacy & AI')
    const notice = summary.closest('details')
    expect(notice).not.toBeNull()
    expect(screen.queryByText('Privacy controls')).not.toBeInTheDocument()
    expect(screen.queryByText('AI is enabled for this account.')).not.toBeInTheDocument()
    expect(within(notice as HTMLElement).getByText('How Artha uses AI and analytics')).toBeVisible()
    await waitFor(() => expect(within(notice as HTMLElement).getByText(/Gemini · gemini-3.5-flash-lite/i)).toBeInTheDocument())
    expect(within(notice as HTMLElement).getByText(/Gemini · gemini-3.5-flash-lite/i)).not.toBeVisible()

    fireEvent.click(summary)

    await waitFor(() => expect(within(notice as HTMLElement).getByText(/Gemini · gemini-3.5-flash-lite/i)).toBeVisible())
    expect(within(notice as HTMLElement).getByText(/cannot write to your ledger/i)).toHaveTextContent(/requires your confirmation/i)
    expect(within(notice as HTMLElement).getByText(/store=false/i)).toBeVisible()
    expect(notice).not.toHaveTextContent(/fictional|pilot/i)
    expect(within(notice as HTMLElement).getByText(/Vercel analytics receives no/i)).toHaveTextContent(/financial text, amounts, emails, account or member names, or assistant questions/i)
  })

  it('explains sample-only policy without claiming personal AI is available', async () => {
    vi.stubEnv('VITE_DEMO_MODE', 'false')
    vi.spyOn(api, 'getManagedAccounts').mockResolvedValue([])
    vi.spyOn(api, 'getAssistantStatus').mockResolvedValue({
      configured: true,
      provider: 'gemini',
      model: 'gemini-3.5-flash-lite',
      available: true,
      dataPolicy: 'sample_only',
      personalDataEnabled: false,
      isDemo: false
    })
    render(<RouterProvider><SettingsPage /></RouterProvider>)

    const summary = screen.getByText('Privacy & AI')
    const notice = summary.closest('details')
    expect(notice).not.toBeNull()
    fireEvent.click(summary)
    expect(await within(notice as HTMLElement).findByText('Private financial text is not sent to AI.')).toBeVisible()
    expect(within(notice as HTMLElement).getByText(/Manual entry remains available/i)).toHaveTextContent(/server policy.*not a browser switch/i)
  })

  it('does not turn a loading status into a private-data guarantee', () => {
    vi.stubEnv('VITE_DEMO_MODE', 'false')
    vi.spyOn(api, 'getManagedAccounts').mockResolvedValue([])
    vi.spyOn(api, 'getAssistantStatus').mockReturnValue(new Promise(() => undefined))

    render(<RouterProvider><SettingsPage /></RouterProvider>)
    const notice = screen.getByText('Privacy & AI').closest('details')
    fireEvent.click(screen.getByText('Privacy & AI'))

    expect(within(notice as HTMLElement).getByText('Checking AI configuration…')).toBeVisible()
    expect(notice).not.toHaveTextContent('Private financial text is not sent to AI.')
  })

  it('reports an unavailable status without guessing the server policy', async () => {
    vi.stubEnv('VITE_DEMO_MODE', 'false')
    vi.spyOn(api, 'getManagedAccounts').mockResolvedValue([])
    vi.spyOn(api, 'getAssistantStatus').mockRejectedValue(new Error('offline'))

    render(<RouterProvider><SettingsPage /></RouterProvider>)
    const notice = screen.getByText('Privacy & AI').closest('details')
    fireEvent.click(screen.getByText('Privacy & AI'))

    expect(await within(notice as HTMLElement).findByText('AI configuration could not be verified.')).toBeVisible()
    expect(within(notice as HTMLElement).getByText(/Do not assume private financial text is blocked or enabled/i)).toBeVisible()
    expect(notice).not.toHaveTextContent('Private financial text is not sent to AI.')
  })

  it('describes a demo runtime as sample-data use, not private-account AI', async () => {
    vi.stubEnv('VITE_DEMO_MODE', 'true')
    vi.spyOn(api, 'getManagedAccounts').mockResolvedValue([])
    vi.spyOn(api, 'getAssistantStatus').mockResolvedValue({
      configured: true,
      provider: 'gemini',
      model: 'gemini-3.5-flash-lite',
      available: true,
      dataPolicy: 'sample_only',
      personalDataEnabled: false,
      isDemo: true
    })

    render(<RouterProvider><SettingsPage /></RouterProvider>)
    const notice = screen.getByText('Privacy & AI').closest('details')
    fireEvent.click(screen.getByText('Privacy & AI'))

    expect(await within(notice as HTMLElement).findByText('AI-assisted features are available for this sample-data experience.')).toBeVisible()
    expect(notice).not.toHaveTextContent('available for this account')
    expect(notice).not.toHaveTextContent('Private financial text is not sent to AI.')
  })

  it('shows every account balance with a reconciliation action', async () => {
    vi.stubEnv('VITE_DEMO_MODE', 'false')
    vi.spyOn(api, 'getAssistantStatus').mockResolvedValue({
      configured: true,
      provider: 'gemini',
      model: 'gemini-3.5-flash-lite',
      available: true,
      dataPolicy: 'private_approved',
      personalDataEnabled: true,
      isDemo: false
    })
    vi.spyOn(api, 'getManagedAccounts').mockResolvedValue([{
      id: 'account-1',
      name: 'Salary Bank',
      kind: 'bank',
      currency: 'INR',
      openingBalancePaise: 100_000,
      currentBalancePaise: 125_000,
      creditLimitPaise: null,
      statementDay: null,
      paymentDueDay: null,
      isArchived: false
    }])

    render(<RouterProvider><SettingsPage /></RouterProvider>)

    const region = await screen.findByRole('region', { name: /Accounts & cards/i })
    expect(within(region).getByText('Salary Bank')).toBeVisible()
    expect(within(region).getByText('₹1,250')).toBeVisible()
    expect(within(region).getByRole('button', { name: /Set actual balance for Salary Bank/i })).toBeVisible()
  })

  it('keeps account input and shows a recoverable create error', async () => {
    vi.stubEnv('VITE_DEMO_MODE', 'false')
    vi.spyOn(api, 'getAssistantStatus').mockResolvedValue({ configured: true, provider: 'gemini', model: 'test', available: true, dataPolicy: 'private_approved', personalDataEnabled: true, isDemo: false })
    vi.spyOn(api, 'getManagedAccounts').mockResolvedValue([])
    vi.spyOn(api, 'createManagedAccount').mockRejectedValue(new Error('An account with this name already exists.'))
    render(<RouterProvider><SettingsPage /></RouterProvider>)

    fireEvent.click(await screen.findByRole('button', { name: 'Add account or card' }))
    fireEvent.change(screen.getByLabelText('Name'), { target: { value: 'ICICI Bank' } })
    fireEvent.click(screen.getByRole('button', { name: 'Add account' }))

    expect(await screen.findByRole('alert')).toHaveTextContent(/already exists/i)
    expect(screen.getByLabelText('Name')).toHaveValue('ICICI Bank')
  })
})
