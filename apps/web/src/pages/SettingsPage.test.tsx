import { cleanup, render, screen, within } from '@testing-library/react'
import { afterEach, describe, expect, it } from 'vitest'
import { RouterProvider } from '../lib/router'
import { SettingsPage } from './SettingsPage'

describe('SettingsPage', () => {
  afterEach(cleanup)

  it('shows an accessible fictional-pilot AI and analytics data-use notice', () => {
    render(<RouterProvider><SettingsPage /></RouterProvider>)

    const notice = screen.getByRole('region', { name: /AI and data use/i })
    expect(within(notice).getByText(/Provider: Gemini/i)).toBeVisible()
    expect(within(notice).getByText(/Purpose:/i)).toHaveTextContent(/reviewable capture drafts.*read-only Ask Artha/i)
    expect(within(notice).getByText(/natural-language capture and Ask Artha/i)).toHaveTextContent(/submitted fictional text or question.*bounded household context.*configured Gemini.*Artha server/i)
    expect(within(notice).getByText(/store=false/i)).toHaveTextContent(/Gemini Interactions requests.*store=false/i)
    expect(within(notice).getByText(/Gemini cannot write to your ledger/i)).toHaveTextContent(/every capture requires review and confirmation/i)
    expect(within(notice).getByText(/real family-finance text is not approved/i)).toBeVisible()
    expect(within(notice).getByText(/Vercel analytics receives no/i)).toHaveTextContent(/financial text, amounts, emails, account or member names, or assistant questions/i)
  })
})
