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
      deterministicFallback: false,
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
      deterministicFallback: false,
      widgets: [{ type: 'line_chart', title: 'Monthly trend', data: [] }]
    })
    const user = userEvent.setup()
    render(<AssistantPage />)

    await user.type(screen.getByLabelText('Ask Artha'), 'Show a trend')
    await user.click(screen.getByRole('button', { name: 'Send question' }))

    expect(await screen.findByText('No data is available for this chart yet.')).toBeInTheDocument()
  })
})
