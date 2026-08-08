import { ArrowLeft, LockKeyhole } from 'lucide-react'
import { RecoveryExportPanel } from '../components/RecoveryPanel'
import { AppLink } from '../lib/router'

export function SettingsPage() {
  return (
    <div className="mx-auto max-w-3xl">
      <AppLink to="/" className="inline-flex min-h-11 items-center gap-2 rounded-xl pr-3 text-sm font-semibold text-[#66736d] tone-muted transition hover:text-moss-800 focus:outline-none focus-visible:ring-2 focus-visible:ring-moss-400"><ArrowLeft className="h-4 w-4" aria-hidden="true" /> Home</AppLink>
      <div className="mt-4 flex items-start gap-3"><span className="grid h-12 w-12 shrink-0 place-items-center rounded-2xl bg-moss-100 text-moss-800"><LockKeyhole className="h-6 w-6" aria-hidden="true" /></span><div><p className="text-sm font-semibold text-moss-700">Recovery</p><h1 className="font-display mt-1 text-balance text-3xl font-bold tracking-[-0.05em] sm:text-4xl">Keep your ledger portable.</h1><p className="mt-3 max-w-2xl text-sm leading-6 text-[#66746d] tone-muted">Create a private encrypted file you control. Restore is offered after sign-in on an account that has not created a ledger yet.</p></div></div>
      <section aria-labelledby="ai-data-use-heading" className="mt-7 rounded-[24px] border border-line bg-white p-4 shadow-card dark:border-night-border dark:bg-night-surface sm:p-6">
        <p className="text-xs font-semibold uppercase tracking-[0.12em] text-moss-700">Fictional pilot</p>
        <h2 id="ai-data-use-heading" className="font-display mt-1 text-lg font-bold">AI and data use</h2>
        <div className="mt-3 space-y-3 text-sm leading-6 text-[#66746d] tone-muted">
          <p>Provider: Gemini, configured server-side.</p>
          <p>Purpose: create reviewable capture drafts and answer read-only Ask Artha ledger questions using bounded household context.</p>
          <p>Natural-language capture and Ask Artha send the submitted fictional text or question, plus bounded household context, to the configured Gemini model through the Artha server.</p>
          <p>Artha sends Gemini Interactions requests with store=false. This describes the request setting only; it is not a broader provider-retention claim and does not approve real family-finance data.</p>
          <p>Gemini cannot write to your ledger. Every capture requires review and confirmation. Real family-finance text is not approved during this fictional pilot.</p>
          <p>Vercel analytics receives no financial text, amounts, emails, account or member names, or assistant questions.</p>
        </div>
      </section>
      <div className="mt-7"><RecoveryExportPanel /></div>
      <div className="mt-5 rounded-2xl border border-line bg-white p-4 text-xs leading-5 text-[#66746d] tone-muted dark:border-night-border dark:bg-night-surface"><strong className="text-ink">Important:</strong> keep the backup file and its passphrase in separate safe places. The encryption happens on this device; Artha never sends the passphrase to its server.</div>
    </div>
  )
}
