import { Bar, BarChart, ResponsiveContainer, Tooltip, XAxis } from 'recharts'
import type { MonthlyPoint } from '../types'
import { formatMoney } from '../lib/money'

export function SpendChart({ data }: { data: MonthlyPoint[] }) {
  return (
    <div className="h-[176px] w-full" aria-label="Six month income and spending chart" role="img">
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={data} barGap={3} margin={{ top: 10, right: 0, bottom: 0, left: 0 }}>
          <XAxis dataKey="month" axisLine={false} tickLine={false} tick={{ fill: '#7c8781', fontSize: 11 }} dy={8} />
          <Tooltip
            cursor={{ fill: '#f3f6f1', radius: 8 }}
            content={({ active, payload, label }) => active && payload?.length ? (
              <div className="rounded-xl border border-line bg-white p-3 text-xs shadow-card">
                <p className="mb-1.5 font-semibold">{label}</p>
                <p className="text-moss-700">Income {formatMoney(Number(payload[0]?.value ?? 0))}</p>
                <p className="text-[#7c8781] tone-muted">Spent {formatMoney(Number(payload[1]?.value ?? 0))}</p>
              </div>
            ) : null}
          />
          <Bar dataKey="incomePaise" fill="#c5ddd1" radius={[5, 5, 3, 3]} maxBarSize={13} />
          <Bar dataKey="spendPaise" fill="#315b4d" radius={[5, 5, 3, 3]} maxBarSize={13} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  )
}
