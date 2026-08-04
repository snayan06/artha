import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { RouterProvider } from '../lib/router'
import type { Transaction } from '../types'
import { localDateOffset } from '../lib/date'
import { QuickAddPage } from './QuickAddPage'

describe('QuickAddPage', () => {
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
    expect(await screen.findByText(/added to your hisab/i)).toBeInTheDocument()
  })

  it('offers a form-first entry with an explicit date picker', async () => {
    const user = userEvent.setup()
    render(<RouterProvider><QuickAddPage onConfirm={vi.fn()} members={[]} /></RouterProvider>)
    await user.click(screen.getByRole('button', { name: 'Enter details manually' }))
    expect(screen.getByLabelText('Transaction date')).toHaveValue(localDateOffset(0))
    expect(screen.getByText(/nothing has been saved yet/i)).toBeInTheDocument()
  })
})
