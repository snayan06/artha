import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { useState } from 'react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { routeIntent } from '../lib/api'
import { UnifiedEntryComposer } from './UnifiedEntryComposer'

vi.mock('../lib/api', () => ({ routeIntent: vi.fn() }))

function renderComposer({
  initialValue = '',
  variant = 'compact'
}: {
  initialValue?: string
  variant?: 'compact' | 'full'
} = {}) {
  const onCapture = vi.fn()
  const onAskLedger = vi.fn()
  function TestComposer() {
    const [value, setValue] = useState(initialValue)
    return (
      <UnifiedEntryComposer
        id="test-entry"
        value={value}
        onChange={setValue}
        variant={variant}
        placeholder="Add or ask"
        onCapture={onCapture}
        onAskLedger={onAskLedger}
      />
    )
  }
  render(
    <TestComposer />
  )
  return { onCapture, onAskLedger }
}

describe('UnifiedEntryComposer', () => {
  afterEach(() => {
    cleanup()
    vi.clearAllMocks()
  })

  it('routes a transaction message to the capture callback', async () => {
    vi.mocked(routeIntent).mockResolvedValue({ intent: 'capture_transaction' })
    const user = userEvent.setup()
    const { onCapture, onAskLedger } = renderComposer()

    await user.type(screen.getByLabelText('Add a transaction or ask Artha'), 'Paid 850 at Zomato')
    await user.click(screen.getByRole('button', { name: 'Continue' }))

    expect(routeIntent).toHaveBeenCalledWith('Paid 850 at Zomato')
    expect(onCapture).toHaveBeenCalledWith('Paid 850 at Zomato')
    expect(onAskLedger).not.toHaveBeenCalled()
  })

  it('normalizes only for routing and preserves the exact message for the workflow', async () => {
    vi.mocked(routeIntent).mockResolvedValue({ intent: 'capture_transaction' })
    const user = userEvent.setup()
    const { onCapture } = renderComposer({ initialValue: '  Paid 250 for coffee  ' })

    await user.click(screen.getByRole('button', { name: 'Continue' }))

    expect(routeIntent).toHaveBeenCalledWith('Paid 250 for coffee')
    expect(onCapture).toHaveBeenCalledWith('  Paid 250 for coffee  ')
  })

  it('routes a ledger question to the assistant callback', async () => {
    vi.mocked(routeIntent).mockResolvedValue({ intent: 'ask_ledger' })
    const user = userEvent.setup()
    const { onCapture, onAskLedger } = renderComposer({ initialValue: 'Show my last three months' })

    await user.click(screen.getByRole('button', { name: 'Continue' }))

    expect(onAskLedger).toHaveBeenCalledWith('Show my last three months')
    expect(onCapture).not.toHaveBeenCalled()
  })

  it('asks the user to choose a path for an ambiguous message', async () => {
    vi.mocked(routeIntent).mockResolvedValue({ intent: 'clarify' })
    const user = userEvent.setup()
    const { onAskLedger } = renderComposer({ initialValue: 'Zomato' })

    await user.click(screen.getByRole('button', { name: 'Continue' }))

    expect(await screen.findByText('What would you like Artha to do with this?')).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Ask about my ledger' }))
    expect(onAskLedger).toHaveBeenCalledWith('Zomato')
  })

  it('preserves the message and offers both paths when routing fails', async () => {
    vi.mocked(routeIntent).mockRejectedValue(new Error('API unavailable'))
    const user = userEvent.setup()
    const { onCapture } = renderComposer({ initialValue: 'Paid or show food' })

    await user.click(screen.getByRole('button', { name: 'Continue' }))

    expect(await screen.findByRole('alert')).toHaveTextContent('Artha could not understand where to send this')
    expect(screen.getByLabelText('Add a transaction or ask Artha')).toHaveValue('Paid or show food')
    await user.click(screen.getByRole('button', { name: 'Add as transaction' }))
    expect(onCapture).toHaveBeenCalledWith('Paid or show food')
  })

  it('keeps an unsupported message editable without invoking a workflow', async () => {
    vi.mocked(routeIntent).mockResolvedValue({ intent: 'unsupported' })
    const user = userEvent.setup()
    const { onCapture, onAskLedger } = renderComposer({ initialValue: 'Help me buy a stock' })

    await user.click(screen.getByRole('button', { name: 'Continue' }))

    expect(await screen.findByRole('alert')).toHaveTextContent('add transactions or answer questions about your ledger')
    expect(screen.getByLabelText('Add a transaction or ask Artha')).toHaveValue('Help me buy a stock')
    expect(onCapture).not.toHaveBeenCalled()
    expect(onAskLedger).not.toHaveBeenCalled()
  })

  it('prevents repeated submission while routing', async () => {
    vi.mocked(routeIntent).mockReturnValue(new Promise(() => undefined))
    const user = userEvent.setup()
    renderComposer({ initialValue: 'Show my balance' })

    await user.dblClick(screen.getByRole('button', { name: 'Continue' }))

    expect(routeIntent).toHaveBeenCalledTimes(1)
    expect(screen.getByRole('status')).toHaveTextContent('Understanding your request')
    expect(screen.getByRole('button', { name: 'Continue' })).toBeDisabled()
  })

  it('submits Enter but keeps Shift+Enter and composing Enter in a full composer', async () => {
    vi.mocked(routeIntent).mockResolvedValue({ intent: 'ask_ledger' })
    const user = userEvent.setup()
    renderComposer({ variant: 'full', initialValue: 'Show my spending' })
    const input = screen.getByLabelText('Add a transaction or ask Artha')

    fireEvent.keyDown(input, { key: 'Enter', shiftKey: true })
    fireEvent.keyDown(input, { key: 'Enter', isComposing: true })
    expect(routeIntent).not.toHaveBeenCalled()

    await user.type(input, '{Enter}')
    expect(routeIntent).toHaveBeenCalledTimes(1)
  })
})
