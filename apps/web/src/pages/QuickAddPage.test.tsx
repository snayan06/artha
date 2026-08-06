import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'
import * as api from '../lib/api'
import { RouterProvider } from '../lib/router'
import type { LedgerAccount, Transaction } from '../types'
import { localDateOffset } from '../lib/date'
import { QuickAddPage } from './QuickAddPage'

describe('QuickAddPage', () => {
  afterEach(() => {
    cleanup()
    vi.restoreAllMocks()
  })

  it('keeps a parsed entry unsaved until explicit confirmation', async () => {
    const user = userEvent.setup()
    const confirmed: Transaction = {
      id: 'new-transaction', kind: 'debit', amountPaise: 85000, personalSharePaise: 42500,
      merchant: 'dinner', category: 'Food & dining', account: 'HDFC UPI', occurredAt: '2026-08-04',
      memberSplits: [{ memberId: '7', memberName: 'Sam', amountPaise: 42500 }], status: 'confirmed'
    }
    const onConfirm = vi.fn().mockResolvedValue(confirmed)
    render(<RouterProvider><QuickAddPage onConfirm={onConfirm} members={[{ id: '7', name: 'Sam' }]} /></RouterProvider>)

    await user.type(screen.getByLabelText(/your message/i), 'Paid 850 for dinner, half with Sam')
    await user.click(screen.getByRole('button', { name: /create review draft/i }))

    expect(await screen.findByText(/nothing has been saved yet/i)).toBeInTheDocument()
    expect(onConfirm).not.toHaveBeenCalled()
    await user.click(screen.getByRole('button', { name: 'Yesterday' }))
    expect(screen.getByLabelText('Transaction date')).toHaveValue(localDateOffset(-1))

    await user.click(screen.getByRole('button', { name: /confirm and add transaction/i }))
    await waitFor(() => expect(onConfirm).toHaveBeenCalledTimes(1))
    expect(await screen.findByText(/added to your artha/i)).toBeInTheDocument()
  })

  it('offers a form-first entry with an explicit date picker', async () => {
    const user = userEvent.setup()
    render(<RouterProvider><QuickAddPage onConfirm={vi.fn()} members={[]} /></RouterProvider>)
    await user.click(screen.getByRole('button', { name: 'Enter details manually' }))
    expect(screen.getByLabelText('Transaction date')).toHaveValue(localDateOffset(0))
    expect(screen.getByText(/nothing has been saved yet/i)).toBeInTheDocument()
  })

  it('preserves the sentence and opens manual entry when AI capture is unavailable', async () => {
    const user = userEvent.setup()
    const sourceText = '  self transfer 25k ICICI -> HDFC  '
    const onConfirm = vi.fn().mockResolvedValue({
      id: 'manual-recovery', kind: 'debit', amountPaise: 25_000, personalSharePaise: 25_000,
      merchant: 'Manual transfer', category: 'Other', account: 'HDFC UPI', occurredAt: localDateOffset(0),
      memberSplits: [], status: 'confirmed'
    } satisfies Transaction)
    vi.spyOn(api, 'parseDraft').mockImplementation(async (text) => {
      throw new api.CaptureDraftUnavailableError(text)
    })
    render(<RouterProvider><QuickAddPage onConfirm={onConfirm} members={[]} /></RouterProvider>)

    await user.type(screen.getByLabelText(/your message/i), sourceText)
    await user.click(screen.getByRole('button', { name: /create review draft/i }))

    expect(await screen.findByRole('alert')).toHaveTextContent(/automatic interpretation is temporarily unavailable/i)
    expect(screen.getByRole('alert')).toHaveTextContent(/your text is still here/i)
    expect(screen.getByLabelText(/your message/i)).toHaveValue(sourceText)
    expect(screen.getByLabelText('Amount in rupees')).toHaveValue(null)
    expect(screen.getByLabelText('Transaction date')).toBeInTheDocument()
    expect(screen.getByText(/nothing has been saved yet/i)).toBeInTheDocument()
    expect(onConfirm).not.toHaveBeenCalled()
    await waitFor(() => expect(screen.getByRole('heading', { name: 'Review the details' })).toHaveFocus())

    await user.type(screen.getByLabelText('Amount in rupees'), '250')
    await user.type(screen.getByLabelText('Description'), 'Manual transfer')
    await user.click(screen.getByRole('button', { name: /confirm and add transaction/i }))

    await waitFor(() => expect(onConfirm).toHaveBeenCalledTimes(1))
    expect(onConfirm.mock.calls[0]?.[0].sourceText).toBe(sourceText)
  })

  it('waits for a real account before confirming a recovered manual draft', async () => {
    const user = userEvent.setup()
    const sourceText = '  Paid 250 for coffee  '
    let resolveAccounts!: (accounts: LedgerAccount[]) => void
    const accountsPromise = new Promise<LedgerAccount[]>((resolve) => {
      resolveAccounts = resolve
    })
    vi.spyOn(api, 'getAccounts').mockReturnValue(accountsPromise)
    vi.spyOn(api, 'parseDraft').mockImplementation(async (text) => {
      throw new api.CaptureDraftUnavailableError(text)
    })
    const onConfirm = vi.fn().mockResolvedValue({
      id: 'account-grounded-recovery', kind: 'debit', amountPaise: 25_000, personalSharePaise: 25_000,
      merchant: 'Coffee', category: 'Other', account: 'ICICI', occurredAt: localDateOffset(0),
      memberSplits: [], status: 'confirmed'
    } satisfies Transaction)
    render(<RouterProvider><QuickAddPage onConfirm={onConfirm} members={[]} /></RouterProvider>)

    await user.type(screen.getByLabelText(/your message/i), sourceText)
    await user.click(screen.getByRole('button', { name: /create review draft/i }))
    await screen.findByRole('alert')
    await user.type(screen.getByLabelText('Amount in rupees'), '250')
    await user.type(screen.getByLabelText('Description'), 'Coffee')
    const confirmButton = screen.getByRole('button', { name: /confirm and add transaction/i })

    expect(confirmButton).toBeDisabled()
    expect(onConfirm).not.toHaveBeenCalled()

    resolveAccounts([{ id: 'account-1', name: 'ICICI', kind: 'bank' }])
    await waitFor(() => expect(screen.getByRole('combobox', { name: 'Paid from account' })).toHaveDisplayValue('ICICI'))
    expect(confirmButton).toBeEnabled()
    await user.click(confirmButton)

    await waitFor(() => expect(onConfirm).toHaveBeenCalledTimes(1))
    expect(onConfirm.mock.calls[0]?.[0]).toEqual(expect.objectContaining({
      sourceAccountId: 'account-1',
      sourceText
    }))
  })

  it('uses accounts that load before an in-flight capture becomes unavailable', async () => {
    const user = userEvent.setup()
    const sourceText = '  Paid 450 for lunch  '
    let resolveAccounts!: (accounts: LedgerAccount[]) => void
    const accountsPromise = new Promise<LedgerAccount[]>((resolve) => {
      resolveAccounts = resolve
    })
    let rejectParse!: (reason?: unknown) => void
    const parsePromise = new Promise<Awaited<ReturnType<typeof api.parseDraft>>>((_, reject) => {
      rejectParse = reject
    })
    vi.spyOn(api, 'getAccounts').mockReturnValue(accountsPromise)
    const parseSpy = vi.spyOn(api, 'parseDraft').mockReturnValue(parsePromise)
    const onConfirm = vi.fn().mockResolvedValue({
      id: 'loaded-before-recovery', kind: 'debit', amountPaise: 45_000, personalSharePaise: 45_000,
      merchant: 'Lunch', category: 'Other', account: 'HDFC', occurredAt: localDateOffset(0),
      memberSplits: [], status: 'confirmed'
    } satisfies Transaction)
    render(<RouterProvider><QuickAddPage onConfirm={onConfirm} members={[]} /></RouterProvider>)

    await user.type(screen.getByLabelText(/your message/i), sourceText)
    await user.click(screen.getByRole('button', { name: /create review draft/i }))
    await waitFor(() => expect(parseSpy).toHaveBeenCalledWith(sourceText, []))

    await act(async () => {
      resolveAccounts([{ id: 'account-2', name: 'HDFC', kind: 'bank' }])
      await accountsPromise
    })
    await act(async () => {
      rejectParse(new api.CaptureDraftUnavailableError(sourceText))
      await Promise.resolve()
    })

    await screen.findByRole('alert')
    expect(screen.getByRole('combobox', { name: 'Paid from account' })).toHaveDisplayValue('HDFC')
    await user.type(screen.getByLabelText('Amount in rupees'), '450')
    await user.type(screen.getByLabelText('Description'), 'Lunch')
    const confirmButton = screen.getByRole('button', { name: /confirm and add transaction/i })
    expect(confirmButton).toBeEnabled()
    await user.click(confirmButton)

    await waitFor(() => expect(onConfirm).toHaveBeenCalledTimes(1))
    expect(onConfirm.mock.calls[0]?.[0]).toEqual(expect.objectContaining({
      sourceAccountId: 'account-2',
      sourceText
    }))
  })

  it('prevents rapid duplicate confirmation while the first write is pending', async () => {
    const user = userEvent.setup()
    let finishConfirmation: ((transaction: Transaction) => void) | undefined
    const pendingConfirmation = new Promise<Transaction>((resolve) => {
      finishConfirmation = resolve
    })
    const onConfirm = vi.fn().mockReturnValue(pendingConfirmation)
    render(<RouterProvider><QuickAddPage onConfirm={onConfirm} members={[]} /></RouterProvider>)

    await user.click(screen.getByRole('button', { name: 'Enter details manually' }))
    await user.type(screen.getByLabelText('Amount in rupees'), '123')
    await user.type(screen.getByLabelText('Description'), 'Coffee')
    const confirmButton = screen.getByRole('button', { name: /confirm and add transaction/i })
    await user.dblClick(confirmButton)

    expect(onConfirm).toHaveBeenCalledTimes(1)
    expect(confirmButton).toBeDisabled()
    finishConfirmation?.({
      id: 'only-once', kind: 'debit', amountPaise: 12_300, personalSharePaise: 12_300,
      merchant: 'Coffee', category: 'Other', account: 'HDFC UPI', occurredAt: localDateOffset(0),
      memberSplits: [], status: 'confirmed'
    })
    expect(await screen.findByText(/added to your artha/i)).toBeInTheDocument()
  })

  it('reuses the reviewed draft idempotency key after a lost response', async () => {
    const user = userEvent.setup()
    const confirmed: Transaction = {
      id: 'replayed', kind: 'debit', amountPaise: 12_300, personalSharePaise: 12_300,
      merchant: 'Coffee', category: 'Other', account: 'HDFC UPI', occurredAt: localDateOffset(0),
      memberSplits: [], status: 'confirmed'
    }
    const onConfirm = vi.fn()
      .mockRejectedValueOnce(new Error('Artha took too long to respond. Please try again.'))
      .mockResolvedValueOnce(confirmed)
    render(<RouterProvider><QuickAddPage onConfirm={onConfirm} members={[]} /></RouterProvider>)

    await user.click(screen.getByRole('button', { name: 'Enter details manually' }))
    await user.type(screen.getByLabelText('Amount in rupees'), '123')
    await user.type(screen.getByLabelText('Description'), 'Coffee')
    const confirmButton = screen.getByRole('button', { name: /confirm and add transaction/i })
    await user.click(confirmButton)
    expect(await screen.findByText(/nothing was saved/i)).toBeInTheDocument()
    await user.click(confirmButton)

    await waitFor(() => expect(onConfirm).toHaveBeenCalledTimes(2))
    expect(onConfirm.mock.calls[0][1]).toBe(onConfirm.mock.calls[1][1])
    expect(await screen.findByText(/added to your artha/i)).toBeInTheDocument()
  })

  it('keeps confirmation disabled for zero or negative amounts', async () => {
    const user = userEvent.setup()
    render(<RouterProvider><QuickAddPage onConfirm={vi.fn()} members={[]} /></RouterProvider>)

    await user.click(screen.getByRole('button', { name: 'Enter details manually' }))
    await user.type(screen.getByLabelText('Description'), 'Invalid amount')
    const amount = screen.getByLabelText('Amount in rupees')
    const confirmButton = screen.getByRole('button', { name: /confirm and add transaction/i })
    expect(confirmButton).toBeDisabled()

    fireEvent.change(amount, { target: { value: '-10' } })
    expect(confirmButton).toBeDisabled()
  })

  it('shows a real destination placeholder for an incomplete transfer', async () => {
    const user = userEvent.setup()
    render(<RouterProvider><QuickAddPage onConfirm={vi.fn()} members={[]} /></RouterProvider>)

    await user.type(screen.getByLabelText(/your message/i), 'transfer 5000 from ICICI')
    await user.click(screen.getByRole('button', { name: /create review draft/i }))

    expect(await screen.findByRole('option', { name: 'Select an account' })).toBeInTheDocument()
    expect(screen.getByRole('combobox', { name: 'Transfer to account' })).toHaveValue('')
    expect(screen.getByText(/choose a destination account/i)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /confirm and add transaction/i })).toBeDisabled()
  })
})
