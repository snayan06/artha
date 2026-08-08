import { cleanup, render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { chatAssistant } from '../lib/api'
import { AssistantPage } from './AssistantPage'

vi.mock('../lib/api', () => ({ chatAssistant: vi.fn() }))

describe('AssistantPage generated UI', () => {
  afterEach(() => {
    cleanup()
    vi.clearAllMocks()
  })

  it('renders generated chart data as an accessible table', async () => {
    vi.mocked(chatAssistant).mockResolvedValue({
      message: 'Here is your spending overview.',
      provider: 'Test provider',
      widgets: [{
        type: 'bar_chart',
        title: 'Monthly spend',
        data: [{ label: 'July', value: 12000 }, { label: 'August', value: 15000 }]
      }]
    })
    const user = userEvent.setup()
    render(<AssistantPage />)

    await user.type(screen.getByLabelText('Ask Artha'), 'Show my monthly spending trend')
    await user.click(screen.getByRole('button', { name: 'Send question' }))

    expect(await screen.findByText('Here is your spending overview.')).toBeInTheDocument()
    const dataTable = screen.getByRole('table', { name: 'Monthly spend values' })
    expect(within(dataTable).getByRole('rowheader', { name: 'August' })).toBeInTheDocument()
    expect(within(dataTable).getByRole('cell', { name: '15000' })).toBeInTheDocument()
  })

  it('renders a chart-specific empty state instead of a broken graph', async () => {
    vi.mocked(chatAssistant).mockResolvedValue({
      message: 'Here is your recent ledger activity.',
      provider: 'Test provider',
      widgets: [{ type: 'line_chart', title: 'Monthly trend', data: [] }]
    })
    const user = userEvent.setup()
    render(<AssistantPage />)

    await user.type(screen.getByLabelText('Ask Artha'), 'Show a trend')
    await user.click(screen.getByRole('button', { name: 'Send question' }))

    expect(await screen.findByText('No data is available for this chart yet.')).toBeInTheDocument()
  })

  it('labels successful model output as an AI response and shows its provider and model', async () => {
    vi.mocked(chatAssistant).mockResolvedValue({
      message: 'Here is your current account overview.',
      provider: 'Gemini · gemini-3.5-flash-lite',
      widgets: [{ type: 'metric', title: 'Available balance', value: '₹12,345' }]
    })
    const user = userEvent.setup()
    render(<AssistantPage />)

    await user.type(screen.getByLabelText('Ask Artha'), 'What is my available balance?')
    await user.click(screen.getByRole('button', { name: 'Send question' }))

    expect(await screen.findByText('AI response')).toBeInTheDocument()
    expect(screen.getByText('Gemini · gemini-3.5-flash-lite')).toBeInTheDocument()
    expect(screen.queryByText('Deterministic fallback')).not.toBeInTheDocument()
  })

  it('restores the exact question after an unavailable response and permits retry without a fake exchange', async () => {
    const scrollTo = vi.fn()
    vi.stubGlobal('scrollTo', scrollTo)
    vi.mocked(chatAssistant)
      .mockRejectedValueOnce(new Error('API request failed (503)'))
      .mockResolvedValueOnce({
        message: 'Here is your current account overview.',
        provider: 'Ollama · qwen3:4b',
        widgets: [{ type: 'metric', title: 'Available balance', value: '₹12,345' }]
      })
    const user = userEvent.setup()
    render(<AssistantPage />)
    const rawQuestion = '  Could I cover a ₹12,000 repair today?  '
    const question = rawQuestion.trim()
    const input = screen.getByLabelText('Ask Artha')

    await user.type(input, rawQuestion)
    await user.click(screen.getByRole('button', { name: 'Send question' }))

    expect(await screen.findByRole('alert')).toHaveTextContent('Artha could not reach the assistant. Your ledger was not changed; please try again.')
    expect(input).toHaveValue(rawQuestion)
    expect(chatAssistant).toHaveBeenNthCalledWith(1, question)
    expect(screen.queryByText(question, { selector: 'section p' })).not.toBeInTheDocument()
    expect(screen.queryByText('Available balance')).not.toBeInTheDocument()
    expect(screen.queryByText('AI response')).not.toBeInTheDocument()
    expect(scrollTo).toHaveBeenCalledWith({ top: 0, behavior: 'auto' })

    await user.click(screen.getByRole('button', { name: 'Send question' }))

    expect(await screen.findByText('Here is your current account overview.')).toBeInTheDocument()
    expect(chatAssistant).toHaveBeenNthCalledWith(2, question)
    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
  })

  it('does not submit a blank-only question', async () => {
    const user = userEvent.setup()
    render(<AssistantPage />)

    await user.type(screen.getByLabelText('Ask Artha'), '   ')

    expect(screen.getByRole('button', { name: 'Send question' })).toBeDisabled()
    expect(chatAssistant).not.toHaveBeenCalled()
  })

  it('disables the textarea while an assistant request is pending', async () => {
    vi.mocked(chatAssistant).mockReturnValue(new Promise(() => undefined))
    const user = userEvent.setup()
    render(<AssistantPage />)
    const input = screen.getByLabelText('Ask Artha')

    await user.type(input, 'Show my balance')
    await user.click(screen.getByRole('button', { name: 'Send question' }))

    expect(await screen.findByRole('status')).toHaveTextContent('Reviewing your ledger…')
    expect(input).toBeDisabled()
  })
})
