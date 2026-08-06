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
      message: 'Your spending increased in August.',
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

    expect(await screen.findByText('Your spending increased in August.')).toBeInTheDocument()
    const dataTable = screen.getByRole('table', { name: 'Monthly spend values' })
    expect(within(dataTable).getByRole('rowheader', { name: 'August' })).toBeInTheDocument()
    expect(within(dataTable).getByRole('cell', { name: '15000' })).toBeInTheDocument()
  })

  it('renders a chart-specific empty state instead of a broken graph', async () => {
    vi.mocked(chatAssistant).mockResolvedValue({
      message: 'There is no matching activity yet.',
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
      message: 'Your available balance is shown below.',
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
    vi.mocked(chatAssistant)
      .mockRejectedValueOnce(new Error('API request failed (503)'))
      .mockResolvedValueOnce({
        message: 'Your available balance is shown below.',
        provider: 'Ollama · qwen3:4b',
        widgets: [{ type: 'metric', title: 'Available balance', value: '₹12,345' }]
      })
    const user = userEvent.setup()
    render(<AssistantPage />)
    const question = 'Could I cover a ₹12,000 repair today?'
    const input = screen.getByLabelText('Ask Artha')

    await user.type(input, question)
    await user.click(screen.getByRole('button', { name: 'Send question' }))

    expect(await screen.findByRole('alert')).toHaveTextContent('Artha could not reach the assistant. Your ledger was not changed; please try again.')
    expect(input).toHaveValue(question)
    expect(screen.queryByText(question, { selector: 'section p' })).not.toBeInTheDocument()
    expect(screen.queryByText('Available balance')).not.toBeInTheDocument()
    expect(screen.queryByText('AI response')).not.toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: 'Send question' }))

    expect(await screen.findByText('Your available balance is shown below.')).toBeInTheDocument()
    expect(chatAssistant).toHaveBeenNthCalledWith(2, question)
    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
  })
})
