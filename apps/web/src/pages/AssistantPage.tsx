import { Bot, ChartNoAxesCombined, LockKeyhole, Send, Sparkles } from 'lucide-react'
import { useState, type FormEvent } from 'react'
import { Bar, BarChart, CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { Badge, Button, Card } from '../components/ui'
import { chatAssistant } from '../lib/api'
import type { AssistantReply, AssistantWidget } from '../types'

interface Exchange {
  id: string
  question: string
  reply: AssistantReply
}

const suggestions = ['Where did I spend the most this month?', 'Show my monthly spending trend', 'What is my available balance?']

export function AssistantPage() {
  const [message, setMessage] = useState('')
  const [history, setHistory] = useState<Exchange[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  async function send(event?: FormEvent) {
    event?.preventDefault()
    const question = message.trim()
    if (!question || loading) return
    setLoading(true)
    setMessage('')
    setError('')
    try {
      const reply = await chatAssistant(question)
      setHistory((current) => [...current, { id: crypto.randomUUID(), question, reply }])
    } catch {
      setError('Artha could not reach the assistant. Your ledger was not changed; please try again.')
      setMessage(question)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="mx-auto max-w-3xl">
      <div className="flex items-start gap-3">
        <span className="grid h-11 w-11 shrink-0 place-items-center rounded-2xl bg-moss-100 text-moss-800"><Bot className="h-5 w-5" /></span>
        <div><p className="flex items-center gap-1.5 text-sm font-semibold text-moss-700"><Sparkles className="h-4 w-4" /> Preview</p><h1 className="font-display mt-1 text-3xl font-bold tracking-[-0.05em] sm:text-4xl">Ask your Artha.</h1><p className="mt-2 text-sm text-[#718078] tone-muted">Get a plain-language view of your ledger. Answers are rendered only as safe, approved widgets.</p></div>
      </div>

      <Card className="mt-6 overflow-hidden">
        <div className="flex items-start gap-3 border-b border-line bg-moss-50 p-4 text-xs text-[#607068] tone-muted sm:items-center">
          <LockKeyhole className="mt-0.5 h-4 w-4 shrink-0 text-moss-700 sm:mt-0" />
          <p>No model HTML is rendered. Verify financial decisions against the transaction list.</p>
        </div>
        <div className="min-h-[280px] space-y-6 p-4 sm:p-6" aria-live="polite">
          {history.length === 0 && <EmptyState onPick={setMessage} />}
          {history.map((exchange) => <ExchangeView key={exchange.id} exchange={exchange} onPick={setMessage} />)}
          {loading && <div className="flex items-center gap-3 text-sm text-[#718078] tone-muted"><span className="h-2 w-2 animate-pulse rounded-full bg-moss-600" /> Reviewing your ledger…</div>}
          {error && <p role="alert" className="rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800">{error}</p>}
        </div>
        <form onSubmit={(event) => void send(event)} className="border-t border-line bg-[#fbfcfa] p-3 dark:bg-night-raised sm:p-4">
          <label htmlFor="assistant-message" className="sr-only">Ask Artha</label>
          <div className="flex items-end gap-2 rounded-[20px] border border-line bg-white p-2 focus-within:border-moss-400 focus-within:ring-4 focus-within:ring-moss-100">
            <textarea id="assistant-message" rows={2} value={message} onChange={(event) => setMessage(event.target.value)} onKeyDown={(event) => { if (event.key === 'Enter' && !event.shiftKey) { event.preventDefault(); void send() } }} placeholder="Ask about spending, balances, or trends…" className="assistant-input min-h-11 flex-1 resize-none border-0 bg-transparent px-2 py-2.5 text-sm outline-none" />
            <Button type="submit" disabled={!message.trim()} loading={loading} className="h-11 w-11 shrink-0 rounded-2xl px-0" aria-label="Send question"><Send className="h-4 w-4" /></Button>
          </div>
        </form>
      </Card>
    </div>
  )
}

function EmptyState({ onPick }: { onPick: (value: string) => void }) {
  return <div className="py-5 text-center"><span className="mx-auto grid h-14 w-14 place-items-center rounded-[20px] bg-moss-50 text-moss-800"><ChartNoAxesCombined className="h-6 w-6" /></span><h2 className="font-display mt-4 text-xl font-bold">Start with a ledger question</h2><div className="mx-auto mt-4 flex max-w-md flex-wrap justify-center gap-2">{suggestions.map((suggestion) => <button key={suggestion} onClick={() => onPick(suggestion)} className="min-h-11 rounded-full border border-line bg-white px-4 text-xs font-semibold text-[#5f6e67] tone-muted hover:border-moss-300 hover:bg-moss-50">{suggestion}</button>)}</div></div>
}

function ExchangeView({ exchange, onPick }: { exchange: Exchange; onPick: (value: string) => void }) {
  return <section className="space-y-3"><p className="ml-auto w-fit max-w-[88%] rounded-[20px] rounded-br-md bg-moss-900 px-4 py-3 text-sm leading-6 text-white dark:bg-[#27604e]">{exchange.question}</p><div className="max-w-[96%] rounded-[20px] rounded-bl-md bg-moss-50 p-4"><div className="mb-3 flex flex-wrap items-center gap-2"><Badge tone={exchange.reply.deterministicFallback ? 'amber' : 'green'}>{exchange.reply.deterministicFallback ? 'Deterministic fallback' : 'Provider response'}</Badge><span className="text-[11px] font-semibold text-[#76837c] tone-muted">{exchange.reply.provider}</span></div><p className="text-sm leading-6">{exchange.reply.message}</p>{exchange.reply.widgets.length > 0 && <div className="mt-4 grid gap-3 sm:grid-cols-2">{exchange.reply.widgets.map((widget, index) => <Widget key={`${widget.type}-${index}`} widget={widget} onPick={onPick} />)}</div>}</div></section>
}

function Widget({ widget, onPick }: { widget: AssistantWidget; onPick: (value: string) => void }) {
  if (widget.type === 'metric') return <Card className="p-4 shadow-none"><p className="text-xs font-semibold uppercase tracking-wider text-[#7b8881] tone-muted">{widget.title}</p><p className="font-display mt-2 text-2xl font-bold tracking-[-0.04em]">{widget.value}</p>{widget.detail && <p className="mt-1 text-xs text-[#748079] tone-muted">{widget.detail}</p>}</Card>
  if (widget.type === 'insight') return <Card className="p-4 shadow-none"><p className="text-sm font-bold">{widget.title}</p><p className="mt-2 text-xs leading-5 text-[#67756e] tone-muted">{widget.body}</p></Card>
  if (widget.type === 'clarification') return <Card className="p-4 shadow-none sm:col-span-2"><p className="text-sm font-bold">{widget.question}</p><div className="mt-3 flex flex-wrap gap-2">{widget.options.map((option) => <button key={option} onClick={() => onPick(option)} className="min-h-11 rounded-full border border-line px-3 text-xs font-semibold hover:border-moss-300">{option}</button>)}</div></Card>
  if (widget.type === 'table') return <Card className="overflow-x-auto p-4 shadow-none sm:col-span-2"><p className="mb-3 text-sm font-bold">{widget.title}</p><table className="w-full min-w-[420px] text-left text-xs"><thead><tr className="border-b border-line">{widget.columns.map((column) => <th key={column} className="px-2 py-2 font-semibold">{column}</th>)}</tr></thead><tbody>{widget.rows.map((row, rowIndex) => <tr key={rowIndex} className="border-b border-line last:border-0">{row.map((cell, cellIndex) => <td key={cellIndex} className="px-2 py-2 text-[#66746d] tone-muted">{cell}</td>)}</tr>)}</tbody></table></Card>
  return <Card className="p-4 shadow-none sm:col-span-2"><p className="mb-3 text-sm font-bold">{widget.title}</p><div className="h-52 w-full"><ResponsiveContainer width="100%" height="100%">{widget.type === 'bar_chart' ? <BarChart data={widget.data}><CartesianGrid vertical={false} stroke="#dfe6e0" strokeDasharray="3 3" /><XAxis dataKey="label" tickLine={false} axisLine={false} fontSize={11} /><YAxis tickLine={false} axisLine={false} fontSize={11} width={38} /><Tooltip /><Bar dataKey="value" fill="#3b715e" radius={[6, 6, 0, 0]} /></BarChart> : <LineChart data={widget.data}><CartesianGrid vertical={false} stroke="#dfe6e0" strokeDasharray="3 3" /><XAxis dataKey="label" tickLine={false} axisLine={false} fontSize={11} /><YAxis tickLine={false} axisLine={false} fontSize={11} width={38} /><Tooltip /><Line type="monotone" dataKey="value" stroke="#3b715e" strokeWidth={3} dot={{ r: 3 }} /></LineChart>}</ResponsiveContainer></div></Card>
}
