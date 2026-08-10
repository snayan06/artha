import { ArrowLeft, LockKeyhole } from 'lucide-react'
import { useEffect, useState } from 'react'
import { RecoveryExportPanel } from '../components/RecoveryPanel'
import { getAssistantStatus } from '../lib/api'
import { AppLink } from '../lib/router'
import type { AssistantRuntimeStatus } from '../types'
import { AccountManagementPanel } from '../components/AccountManagementPanel'

export function SettingsPage() {
  const [assistantStatus, setAssistantStatus] = useState<AssistantRuntimeStatus | null>(null)

  useEffect(() => {
    let active = true
    void getAssistantStatus()
      .then((status) => { if (active) setAssistantStatus(status) })
      .catch(() => { if (active) setAssistantStatus(null) })
    return () => { active = false }
  }, [])

  const provider = assistantStatus
    ? `${assistantStatus.provider === 'gemini' ? 'Gemini' : assistantStatus.provider}${assistantStatus.model ? ` · ${assistantStatus.model}` : ''}`
    : 'Checking configuration…'

  return (
    <div className="mx-auto max-w-3xl">
      <AppLink to="/" className="inline-flex min-h-11 items-center gap-2 rounded-xl pr-3 text-sm font-semibold text-[#66736d] tone-muted transition hover:text-moss-800 focus:outline-none focus-visible:ring-2 focus-visible:ring-moss-400"><ArrowLeft className="h-4 w-4" aria-hidden="true" /> Home</AppLink>
      <div className="mt-4 flex items-start gap-3"><span className="grid h-12 w-12 shrink-0 place-items-center rounded-2xl bg-moss-100 text-moss-800"><LockKeyhole className="h-6 w-6" aria-hidden="true" /></span><div><p className="text-sm font-semibold text-moss-700">Recovery</p><h1 className="font-display mt-1 text-balance text-3xl font-bold tracking-[-0.05em] sm:text-4xl">Keep your ledger portable.</h1><p className="mt-3 max-w-2xl text-sm leading-6 text-[#66746d] tone-muted">Create a private encrypted file you control. Restore is offered after sign-in on an account that has not created a ledger yet.</p></div></div>
      <section aria-labelledby="ai-data-use-heading" className="mt-7 rounded-[24px] border border-line bg-white p-4 shadow-card dark:border-night-border dark:bg-night-surface sm:p-6">
        <p className="text-xs font-semibold uppercase tracking-[0.12em] text-moss-700">Privacy controls</p>
        <h2 id="ai-data-use-heading" className="font-display mt-1 text-lg font-bold">AI and data use</h2>
        <div className="mt-4 rounded-2xl bg-moss-50 p-4 text-sm leading-6 text-moss-900 dark:bg-night-raised dark:text-night-ink">
          <p className="font-bold">{assistantStatus?.personalDataEnabled ? 'AI is enabled for this account.' : assistantStatus?.isDemo ? 'AI is enabled for sample data.' : 'Private financial text is not sent to AI.'}</p>
          <p className="mt-1">{assistantStatus?.personalDataEnabled || assistantStatus?.isDemo ? 'AI can prepare capture drafts and read-only answers. It cannot write to your ledger; every transaction still requires your confirmation.' : 'Manual entry remains available. This protection is controlled by the server policy, not a browser switch.'}</p>
        </div>
        <details className="mt-4 rounded-2xl border border-line px-4 py-3 text-sm text-[#66746d] tone-muted">
          <summary className="min-h-11 cursor-pointer py-2 font-semibold text-ink focus:outline-none focus-visible:ring-2 focus-visible:ring-moss-400">Provider and data details</summary>
          <div className="space-y-3 pb-2 pt-2 leading-6">
            <p>Provider: {provider}, configured server-side.</p>
            <p>When enabled, capture sends your submitted text and relevant account, category and household choices. Ask Artha sends your question with a limited ledger summary.</p>
            <p>Requests use <code>store=false</code>. This request setting is not a broader provider-retention guarantee.</p>
            <p>Vercel analytics receives no financial text, amounts, emails, account or member names, or assistant questions.</p>
          </div>
        </details>
      </section>
      <AccountManagementPanel />
      <div className="mt-7"><RecoveryExportPanel /></div>
      <div className="mt-5 rounded-2xl border border-line bg-white p-4 text-xs leading-5 text-[#66746d] tone-muted dark:border-night-border dark:bg-night-surface"><strong className="text-ink">Important:</strong> keep the backup file and its passphrase in separate safe places. The encryption happens on this device; Artha never sends the passphrase to its server.</div>
    </div>
  )
}
