import { Monitor, Moon, Sun } from 'lucide-react'
import { useEffect, useState } from 'react'
import { applyTheme, getThemePreference, saveThemePreference, type ThemePreference } from '../lib/theme'

const nextTheme: Record<ThemePreference, ThemePreference> = { system: 'light', light: 'dark', dark: 'system' }
const labels: Record<ThemePreference, string> = { system: 'System', light: 'Light', dark: 'Dark' }

export function ThemeControl() {
  const [preference, setPreference] = useState<ThemePreference>(getThemePreference)

  useEffect(() => {
    applyTheme(preference)
    const media = window.matchMedia('(prefers-color-scheme: dark)')
    const updateSystem = () => { if (preference === 'system') applyTheme('system') }
    media.addEventListener('change', updateSystem)
    return () => media.removeEventListener('change', updateSystem)
  }, [preference])

  function cycle() {
    const next = nextTheme[preference]
    saveThemePreference(next)
    setPreference(next)
  }

  const Icon = preference === 'dark' ? Moon : preference === 'light' ? Sun : Monitor
  return <button onClick={cycle} className="grid h-11 w-11 place-items-center rounded-full border border-line bg-white text-[#66736d] tone-muted transition hover:bg-moss-50 focus:outline-none focus-visible:ring-2 focus-visible:ring-moss-400" aria-label={`Theme: ${labels[preference]}. Change theme`} title={`Theme: ${labels[preference]}`}><Icon className="h-5 w-5" /></button>
}
