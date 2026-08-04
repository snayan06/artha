import { ArrowLeft, Check, ChevronRight, Info, RotateCcw, ShieldCheck, Sparkles, UsersRound } from 'lucide-react'
import { useEffect, useState } from 'react'
import { Badge, Button, Card } from '../components/ui'
import { getAccounts, parseDraft } from '../lib/api'
import { formatMoney, rupeesToPaise } from '../lib/money'
import { localDateOffset } from '../lib/date'
import { useRouter } from '../lib/router'
import type { HouseholdMember, LedgerAccount, Transaction, TransactionDraft } from '../types'

export function QuickAddPage({ onConfirm, members }: { onConfirm: (draft: TransactionDraft) => Promise<Transaction>; members: HouseholdMember[] }) {
  const { state, navigate, back } = useRouter()
  const initialCapture = (state as { capture?: string } | null)?.capture ?? ''
  const [capture, setCapture] = useState(initialCapture)
  const [draft, setDraft] = useState<TransactionDraft | null>(null)
  const [parsing, setParsing] = useState(false)
  const [saving, setSaving] = useState(false)
  const [success, setSuccess] = useState<Transaction | null>(null)
  const [error, setError] = useState('')
  const [usedFallback, setUsedFallback] = useState(false)
  const [accounts, setAccounts] = useState<LedgerAccount[]>([])
  const starterPrompts = [members[0] ? `Paid 850 for dinner yesterday, split with ${members[0].name}` : 'Paid 850 for dinner yesterday', 'Received 45,000 salary today in ICICI Bank', 'Spent 320 on Uber from HDFC Card']

  useEffect(() => {
    void getAccounts().then((loadedAccounts) => {
      setAccounts(loadedAccounts)
      setDraft((current) => current && current.sourceText === '' && current.sourceAccountId === undefined && loadedAccounts[0]
        ? { ...current, account: loadedAccounts[0].name, sourceAccountId: loadedAccounts[0].id }
        : current)
    })
  }, [])

  useEffect(() => {
    if (initialCapture) void makeDraft(initialCapture)
    // The initial route state is intentionally parsed once.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  async function makeDraft(text = capture) {
    if (!text.trim()) return
    setParsing(true)
    setError('')
    try {
      const response = await parseDraft(text.trim(), members)
      setDraft(response.data)
      setUsedFallback(response.demo)
    } catch {
      setError('We could not read that. Try including an amount and what it was for.')
    } finally {
      setParsing(false)
    }
  }

  async function confirm() {
    if (!draft || draft.amountPaise <= 0) return
    setSaving(true)
    setError('')
    try {
      const transaction = await onConfirm(draft)
      setSuccess(transaction)
    } catch {
      setError('This draft was not saved. Please try again.')
    } finally {
      setSaving(false)
    }
  }

  function restart() {
    setCapture('')
    setDraft(null)
    setSuccess(null)
    setError('')
  }

  function startManualEntry() {
    const firstAccount = accounts[0]
    setDraft({ kind: 'debit', amountPaise: 0, merchant: '', category: 'Other', account: firstAccount?.name ?? 'Primary account', sourceAccountId: firstAccount?.id, occurredAt: localDateOffset(0), note: '', memberSplits: [], confidence: 'review', sourceText: '' })
    setUsedFallback(false)
    setError('')
  }

  if (success) {
    return (
      <div className="mx-auto max-w-xl pt-8 sm:pt-16">
        <Card className="p-6 text-center sm:p-10">
          <div className="mx-auto grid h-16 w-16 place-items-center rounded-full bg-moss-100 text-moss-800"><Check className="h-8 w-8" strokeWidth={2.5} /></div>
          <Badge tone="green"><span className="mr-1">●</span> Confirmed</Badge>
          <h1 className="font-display mt-4 text-2xl font-bold tracking-[-0.04em]">Added to your Hisab</h1>
          <p className="font-display mt-3 text-4xl font-bold tracking-[-0.05em]">{formatMoney(success.amountPaise)}</p>
          <p className="mt-2 text-sm text-[#718078] tone-muted">{success.merchant} · {success.account}</p>
          {success.memberSplits.length > 0 && <div className="mt-4 flex flex-wrap justify-center gap-2">{success.memberSplits.map((split) => <p key={split.memberId} className="inline-flex items-center gap-1.5 rounded-xl bg-moss-50 px-3 py-2 text-xs font-semibold text-moss-800"><UsersRound className="h-4 w-4" /> {split.memberName}: {formatMoney(split.amountPaise)}</p>)}</div>}
          <div className="mt-8 grid gap-3 sm:grid-cols-2">
            <Button variant="secondary" onClick={restart} icon={<RotateCcw className="h-4 w-4" />}>Add another</Button>
            <Button onClick={() => navigate('/')}>Back home <ChevronRight className="h-4 w-4" /></Button>
          </div>
        </Card>
      </div>
    )
  }

  return (
    <div className="mx-auto max-w-2xl">
      <button onClick={back} className="mb-5 inline-flex min-h-11 items-center gap-2 rounded-xl py-2 pr-3 text-sm font-semibold text-[#66736d] tone-muted hover:text-moss-800"><ArrowLeft className="h-4 w-4" /> Back</button>
      <div className="mb-6">
        <div className="flex items-center gap-2 text-sm font-semibold text-moss-700"><Sparkles className="h-4 w-4" /> Quick add</div>
        <h1 className="font-display mt-2 text-3xl font-bold tracking-[-0.05em] sm:text-4xl">Tell us what happened.</h1>
        <p className="mt-2 text-sm text-[#718078] tone-muted">Write naturally. You’ll review every detail before it is saved.</p>
      </div>

      <Card className="p-4 sm:p-5">
        <label htmlFor="capture" className="text-xs font-bold uppercase tracking-[0.12em] text-[#78847e] tone-muted">Your message</label>
        <textarea id="capture" rows={3} value={capture} onChange={(event) => setCapture(event.target.value)} placeholder={members[0] ? `Paid 1,840 for groceries yesterday, split with ${members[0].name}` : 'Paid 1,840 for groceries yesterday'} className="mt-2 w-full resize-none rounded-2xl border border-line bg-[#fafbf9] p-4 text-base leading-6 outline-none transition placeholder:text-[#a0aaa4] tone-subtle focus:border-moss-400 focus:ring-4 focus:ring-moss-100 dark:bg-night-input" />
        <div className="mt-3 grid gap-2 sm:flex"><Button className="w-full sm:w-auto" disabled={!capture.trim()} loading={parsing} onClick={() => void makeDraft()}>Create review draft <ChevronRight className="h-4 w-4" /></Button><Button variant="secondary" className="w-full sm:w-auto" onClick={startManualEntry}>Enter details manually</Button></div>
        {!draft && (
          <div className="mt-5 border-t border-line pt-4">
            <p className="mb-2 text-[11px] font-semibold uppercase tracking-wider text-[#8a958f] tone-subtle">Try an example</p>
            <div className="flex gap-2 overflow-x-auto pb-1 scrollbar-none">
              {starterPrompts.map((prompt) => <button key={prompt} onClick={() => { setCapture(prompt); void makeDraft(prompt) }} className="shrink-0 rounded-full border border-line bg-white px-3 py-2 text-xs text-[#5d6a64] tone-muted hover:border-moss-300">{prompt}</button>)}
            </div>
          </div>
        )}
      </Card>

      {error && <div role="alert" className="mt-4 rounded-2xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800">{error}</div>}

      {draft && (
        <section className="mt-5" aria-labelledby="review-heading">
          <div className="mb-3 flex items-center justify-between">
            <div>
              <p className="text-xs font-semibold uppercase tracking-[0.12em] text-[#88938d] tone-subtle">Unsaved draft</p>
              <h2 id="review-heading" className="font-display mt-1 text-xl font-bold">Review the details</h2>
            </div>
            <Badge tone={draft.confidence === 'high' ? 'green' : 'amber'}>{draft.confidence === 'high' ? 'Looks good' : 'Needs review'}</Badge>
          </div>

          <Card className="overflow-hidden">
            <div className="bg-moss-50 p-5 text-center">
              <p className="text-xs font-semibold uppercase tracking-[0.14em] text-moss-700">{draft.kind === 'credit' ? 'Money received' : 'Money spent'}</p>
              <div className="mt-2 flex items-center justify-center text-4xl font-bold tracking-[-0.05em]">
                <span className="mr-1 text-2xl text-moss-700">₹</span>
                <input aria-label="Amount in rupees" inputMode="decimal" value={draft.amountPaise ? draft.amountPaise / 100 : ''} onChange={(event) => { const amountPaise = rupeesToPaise(Number(event.target.value) || 0); setDraft({ ...draft, amountPaise, memberSplits: equalSplits(amountPaise, draft.memberSplits.map((split) => split.memberId), members) }) }} className="min-h-11 w-40 border-0 bg-transparent text-center outline-none" />
              </div>
            </div>

            <div className="grid gap-x-4 p-5 sm:grid-cols-2">
              <DraftField label="Description" value={draft.merchant} onChange={(value) => setDraft({ ...draft, merchant: value })} />
              <DraftField label="Category" value={draft.category} onChange={(value) => setDraft({ ...draft, category: value })} />
              <AccountField accounts={accounts} draft={draft} onChange={(account) => setDraft({ ...draft, account: account.name, sourceAccountId: account.id })} />
              <DateField value={draft.occurredAt} onChange={(value) => setDraft({ ...draft, occurredAt: value })} />
            </div>

            {members.length > 0 && <div className="mx-5 mb-5 rounded-2xl border border-moss-200 bg-moss-50 p-4">
              <div className="flex items-center gap-3"><span className="grid h-9 w-9 place-items-center rounded-xl bg-white text-moss-800"><UsersRound className="h-4 w-4" /></span><span><span className="block text-sm font-semibold">Share this expense</span><span className="mt-0.5 block text-xs text-[#748079] tone-muted">Choose anyone involved. Shares are equal in V1.</span></span></div>
              <div className="mt-4 grid gap-2 sm:grid-cols-2">{members.map((member) => { const checked = draft.memberSplits.some((split) => split.memberId === member.id); return <label key={member.id} className="flex min-h-11 cursor-pointer items-center justify-between rounded-xl border border-moss-200 bg-white px-3 text-sm font-semibold"><span className="truncate">{member.name}</span><input type="checkbox" aria-label={`Share with ${member.name}`} checked={checked} onChange={(event) => { const selected = event.target.checked ? [...draft.memberSplits.map((split) => split.memberId), member.id] : draft.memberSplits.map((split) => split.memberId).filter((id) => id !== member.id); setDraft({ ...draft, memberSplits: equalSplits(draft.amountPaise, selected, members) }) }} className="h-5 w-5 accent-moss-800" /></label> })}</div>
              {draft.memberSplits.length > 0 && (
                <div className="mt-4 grid grid-cols-3 gap-2 border-t border-moss-200 pt-4 text-center text-xs">
                  <div><p className="text-[#7a867f] tone-muted">Account moves</p><p className="mt-1 font-bold">−{formatMoney(draft.amountPaise)}</p></div>
                  <div><p className="text-[#7a867f] tone-muted">Your share</p><p className="mt-1 font-bold">{formatMoney(draft.amountPaise - draft.memberSplits.reduce((sum, split) => sum + split.amountPaise, 0))}</p></div>
                  <div><p className="text-[#7a867f] tone-muted">Family share</p><p className="mt-1 font-bold text-moss-800">{formatMoney(draft.memberSplits.reduce((sum, split) => sum + split.amountPaise, 0))}</p></div>
                </div>
              )}
            </div>}

            <div className="border-t border-line bg-[#fbfcfa] p-5 dark:bg-night-raised">
              <div className="mb-4 flex items-start gap-2 text-xs text-[#6f7b75] tone-muted"><ShieldCheck className="mt-0.5 h-4 w-4 shrink-0 text-moss-700" /><p><strong className="text-ink">Nothing has been saved yet.</strong> Confirm only after these details look right.{usedFallback && ' Parsed safely on this device while the API is unavailable.'}</p></div>
              <Button onClick={() => void confirm()} loading={saving} disabled={!draft.amountPaise || !draft.merchant.trim()} className="w-full" icon={<Check className="h-4 w-4" />}>Confirm and add transaction</Button>
            </div>
          </Card>
          {draft.confidence === 'review' && <p className="mt-3 flex items-center gap-2 text-xs text-amber-800"><Info className="h-4 w-4" /> One or more fields were inferred with low confidence. Please check them carefully.</p>}
        </section>
      )}
    </div>
  )
}

function equalSplits(amountPaise: number, selectedIds: string[], members: HouseholdMember[]): TransactionDraft['memberSplits'] {
  const uniqueIds = [...new Set(selectedIds)]
  const sharePaise = uniqueIds.length ? Math.floor(amountPaise / (uniqueIds.length + 1)) : 0
  return uniqueIds.flatMap((memberId) => {
    const member = members.find((item) => item.id === memberId)
    return member ? [{ memberId, memberName: member.name, amountPaise: sharePaise }] : []
  })
}

function DraftField({ label, value, type = 'text', onChange }: { label: string; value: string; type?: string; onChange: (value: string) => void }) {
  return (
    <label className="mb-4 block">
      <span className="text-[11px] font-semibold uppercase tracking-[0.1em] text-[#87928c] tone-subtle">{label}</span>
      <input type={type} value={value} onChange={(event) => onChange(event.target.value)} className="mt-1.5 min-h-11 w-full rounded-xl border border-line bg-white px-3 text-sm font-semibold outline-none focus:border-moss-400 focus:ring-3 focus:ring-moss-100" />
    </label>
  )
}

function AccountField({ accounts, draft, onChange }: { accounts: LedgerAccount[]; draft: TransactionDraft; onChange: (account: LedgerAccount) => void }) {
  const options = accounts.some((account) => account.id === draft.sourceAccountId && account.name === draft.account) ? accounts : [{ id: draft.sourceAccountId, name: draft.account, kind: 'bank' as const }, ...accounts]
  const selectedIndex = Math.max(0, options.findIndex((account) => account.id === draft.sourceAccountId && account.name === draft.account))
  return (
    <label className="mb-4 block">
      <span className="text-[11px] font-semibold uppercase tracking-[0.1em] text-[#87928c] tone-subtle">Paid from</span>
      <select aria-label="Paid from account" value={String(selectedIndex)} onChange={(event) => onChange(options[Number(event.target.value)])} className="mt-1.5 min-h-11 w-full rounded-xl border border-line bg-white px-3 text-sm font-semibold outline-none focus:border-moss-400 focus:ring-3 focus:ring-moss-100">
        {options.map((account, index) => <option key={`${account.id ?? 'demo'}-${account.name}-${index}`} value={String(index)}>{account.name}</option>)}
      </select>
    </label>
  )
}

function DateField({ value, onChange }: { value: string; onChange: (value: string) => void }) {
  const today = localDateOffset(0)
  const yesterday = localDateOffset(-1)
  return (
    <div className="mb-4">
      <label className="block"><span className="text-[11px] font-semibold uppercase tracking-[0.1em] text-[#87928c] tone-subtle">Date</span><input aria-label="Transaction date" type="date" value={value} onChange={(event) => onChange(event.target.value)} className="mt-1.5 min-h-11 w-full rounded-xl border border-line bg-white px-3 text-sm font-semibold outline-none focus:border-moss-400 focus:ring-4 focus:ring-moss-100" /></label>
      <div className="mt-2 grid grid-cols-2 gap-2"><button type="button" onClick={() => onChange(today)} aria-pressed={value === today} className={`min-h-11 rounded-xl border px-3 text-xs font-semibold transition ${value === today ? 'border-moss-700 bg-moss-100 text-moss-900' : 'border-line bg-white text-[#68756e] tone-muted'}`}>Today</button><button type="button" onClick={() => onChange(yesterday)} aria-pressed={value === yesterday} className={`min-h-11 rounded-xl border px-3 text-xs font-semibold transition ${value === yesterday ? 'border-moss-700 bg-moss-100 text-moss-900' : 'border-line bg-white text-[#68756e] tone-muted'}`}>Yesterday</button></div>
    </div>
  )
}
