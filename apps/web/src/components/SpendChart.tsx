import { Bar, BarChart, ResponsiveContainer, Tooltip, XAxis } from 'recharts'
import type { MonthlyPoint } from '../types'
import { formatMoney } from '../lib/money'

export function SpendChart({ data }: { data: MonthlyPoint[] }) {
  if (data.length === 0) {
    return <div className="grid h-[176px] place-items-center rounded-2xl bg-moss-50 px-4 text-center text-sm text-[#6e7b74] tone-muted" role="status">No monthly activity to chart yet.</div>
  }

  return (
    <figure>
      <figcaption className="sr-only">Six-month income and spending chart. A data table follows.</figcaption>
      <div className="h-[176px] w-full" aria-hidden="true">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={data} barGap={3} margin={{ top: 10, right: 0, bottom: 0, left: 0 }}>
            <XAxis dataKey="month" axisLine={false} tickLine={false} tick={{ fill: 'var(--chart-axis)', fontSize: 11 }} dy={8} />
            <Tooltip
              cursor={{ fill: 'rgba(122, 135, 129, 0.12)', radius: 8 }}
              content={({ active, payload, label }) => active && payload?.length ? (
                <div className="rounded-xl border border-line bg-white p-3 text-xs shadow-card">
                  <p className="mb-1.5 font-semibold">{label}</p>
                  <p className="text-moss-700">Income {formatMoney(Number(payload[0]?.value ?? 0))}</p>
                  <p className="text-[#7c8781] tone-muted">Spent {formatMoney(Number(payload[1]?.value ?? 0))}</p>
                </div>
              ) : null}
            />
            <Bar dataKey="incomePaise" fill="var(--chart-income)" radius={[5, 5, 3, 3]} maxBarSize={13} isAnimationActive={false} />
            <Bar dataKey="spendPaise" fill="var(--chart-series)" radius={[5, 5, 3, 3]} maxBarSize={13} isAnimationActive={false} />
          </BarChart>
        </ResponsiveContainer>
      </div>
      <div className="sr-only">
        <table className="tabular-nums">
          <caption>Six-month income and spending values</caption>
          <thead><tr><th scope="col">Month</th><th scope="col">Income</th><th scope="col">Spending</th></tr></thead>
          <tbody>{data.map((point) => <tr key={point.month}><th scope="row">{point.month}</th><td>{formatMoney(point.incomePaise)}</td><td>{formatMoney(point.spendPaise)}</td></tr>)}</tbody>
        </table>
      </div>
    </figure>
  )
}
