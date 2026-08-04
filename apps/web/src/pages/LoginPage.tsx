import { Mail, ShieldCheck } from 'lucide-react'
import { useState } from 'react'
import { ThemeControl } from '../components/ThemeControl'
import { Button, Card } from '../components/ui'

export function LoginPage({
  configurationError,
  onSendLink
}: {
  configurationError?: string | null
  onSendLink: (email: string) => Promise<void>
}) {
  const [email, setEmail] = useState('')
  const [sending, setSending] = useState(false)
  const [sent, setSent] = useState(false)
  const [error, setError] = useState('')

  async function submit(event: React.FormEvent) {
    event.preventDefault()
    if (configurationError || !email.trim()) return
    setSending(true)
    setError('')
    setSent(false)
    try {
      await onSendLink(email.trim())
      setSent(true)
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'The sign-in link could not be sent.')
    } finally {
      setSending(false)
    }
  }

  return (
    <main className="min-h-screen bg-canvas px-4 py-8 text-ink sm:grid sm:place-items-center">
      <div className="mx-auto w-full max-w-md">
        <header className="mb-8 flex items-center justify-between">
          <div className="flex min-h-11 items-center gap-3">
            <span className="grid h-10 w-10 place-items-center rounded-[14px] bg-moss-900 font-display text-xl font-bold text-white dark:bg-[#27604e]">H</span>
            <div><p className="font-display text-lg font-bold leading-none">Hisab</p><p className="mt-1 text-[10px] font-semibold uppercase tracking-[0.16em] text-[#839089] tone-subtle">Private ledger</p></div>
          </div>
          <ThemeControl />
        </header>

        <Card className="p-6 sm:p-8">
          <span className="grid h-12 w-12 place-items-center rounded-2xl bg-moss-100 text-moss-800"><ShieldCheck className="h-6 w-6" /></span>
          <h1 className="font-display mt-5 text-3xl font-bold tracking-[-0.05em]">Sign in to your ledger</h1>
          <p className="mt-3 text-sm leading-6 text-[#6e7b74] tone-muted">We’ll email you a secure magic link. No password is stored by Hisab.</p>

          <form className="mt-7" onSubmit={(event) => void submit(event)}>
            <label className="block" htmlFor="login-email">
              <span className="mb-1.5 block text-[11px] font-semibold uppercase tracking-[0.1em] text-[#7c8882] tone-muted">Email address</span>
              <span className="relative block">
                <Mail className="pointer-events-none absolute left-3.5 top-1/2 h-4 w-4 -translate-y-1/2 text-[#7c8882]" />
                <input id="login-email" type="email" inputMode="email" autoComplete="email" required value={email} onChange={(event) => setEmail(event.target.value)} disabled={Boolean(configurationError)} placeholder="you@example.com" className="min-h-12 w-full rounded-xl border border-line bg-white pl-10 pr-3 text-sm font-semibold outline-none transition focus:border-moss-400 focus:ring-4 focus:ring-moss-100 disabled:cursor-not-allowed disabled:opacity-60" />
              </span>
            </label>
            <Button type="submit" loading={sending} disabled={Boolean(configurationError) || !email.trim()} className="mt-4 w-full">Email me a sign-in link</Button>
          </form>

          {configurationError && <p role="alert" className="mt-4 rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800">{configurationError}</p>}
          {error && <p role="alert" className="mt-4 rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800">{error}</p>}
          {sent && <p role="status" className="mt-4 rounded-xl border border-moss-200 bg-moss-50 px-4 py-3 text-sm text-moss-900">Check your email and open the link on this device to continue.</p>}
        </Card>
      </div>
    </main>
  )
}

export function SessionLoadingPage() {
  return <main className="grid min-h-screen place-items-center bg-canvas px-4 text-ink"><div role="status" aria-live="polite" className="text-center"><span className="mx-auto block h-8 w-8 animate-spin rounded-full border-2 border-moss-200 border-t-moss-800" /><p className="mt-4 text-sm font-semibold">Loading your secure session…</p></div></main>
}
