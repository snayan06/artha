import { afterEach, describe, expect, it, vi } from 'vitest'
import { applyTheme, getThemePreference, saveThemePreference } from './theme'

describe('theme preference', () => {
  afterEach(() => {
    document.documentElement.className = ''
    document.documentElement.removeAttribute('data-theme')
    localStorage.clear()
    vi.restoreAllMocks()
  })

  it('applies and persists a real dark theme', () => {
    saveThemePreference('dark')
    expect(getThemePreference()).toBe('dark')
    expect(document.documentElement).toHaveClass('dark')
    expect(document.documentElement.dataset.theme).toBe('dark')
  })

  it('applies light and follows system preference', () => {
    applyTheme('light')
    expect(document.documentElement).not.toHaveClass('dark')
    vi.spyOn(window, 'matchMedia').mockReturnValue({ matches: true } as MediaQueryList)
    expect(applyTheme('system')).toBe('dark')
    expect(document.documentElement).toHaveClass('dark')
  })
})
