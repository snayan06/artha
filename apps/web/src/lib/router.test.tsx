import { fireEvent, render, screen } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { AppLink, RouterProvider } from './router'

describe('RouterProvider', () => {
  beforeEach(() => {
    window.history.replaceState(null, '', '/add')
  })

  it('resets scroll immediately when navigating to another page', () => {
    const scrollTo = vi.fn()
    vi.stubGlobal('scrollTo', scrollTo)

    render(
      <RouterProvider>
        <AppLink to="/assistant">Open assistant</AppLink>
      </RouterProvider>
    )

    fireEvent.click(screen.getByRole('link', { name: 'Open assistant' }))

    expect(window.location.pathname).toBe('/assistant')
    expect(scrollTo).toHaveBeenCalledWith({ top: 0, behavior: 'auto' })
  })
})
