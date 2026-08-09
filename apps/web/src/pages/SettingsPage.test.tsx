import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import * as api from '../lib/api'
import { RouterProvider } from '../lib/router'
import { SettingsPage } from './SettingsPage'

describe('SettingsPage', () => {
  afterEach(() => {
    cleanup()
    vi.restoreAllMocks()
  })

  it('shows the server-owned private-data policy and analytics notice', async () => {
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

    const notice = screen.getByRole('region', { name: /AI and data use/i })
    await waitFor(() => expect(within(notice).getByText(/Gemini · gemini-3.5-flash-lite/i)).toBeVisible())
    expect(within(notice).getByText(/Purpose:/i)).toHaveTextContent(/reviewable capture drafts.*read-only Ask Artha/i)
    expect(within(notice).getByText(/Natural-language capture and Ask Artha/i)).toHaveTextContent(/submitted text or question.*bounded household context.*configured AI provider.*Artha server/i)
    expect(within(notice).getByText(/store=false/i)).toHaveTextContent(/Gemini Interactions requests.*store=false/i)
    expect(within(notice).getByText(/Gemini cannot write to your ledger/i)).toHaveTextContent(/every capture requires review and confirmation/i)
    expect(within(notice).getByText(/Private-data AI access/i).closest('p')).toHaveTextContent(/enabled for this deployment/i)
    expect(notice).not.toHaveTextContent(/fictional|pilot/i)
    expect(within(notice).getByText(/Vercel analytics receives no/i)).toHaveTextContent(/financial text, amounts, emails, account or member names, or assistant questions/i)
  })

  it('explains sample-only policy without claiming personal AI is available', async () => {
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

    const notice = screen.getByRole('region', { name: /AI and data use/i })
    expect((await within(notice).findByText(/Private-data AI access/i)).closest('p')).toHaveTextContent(/not enabled.*manual entry remains available/i)
  })

  it('shows every account balance with a reconciliation action', async () => {
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
