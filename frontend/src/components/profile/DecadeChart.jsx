import { BarChart, Bar, XAxis, YAxis, ResponsiveContainer, Tooltip, Cell } from 'recharts'
import { TOOLTIP_STYLE } from '../../lib/chartTheme'

export default function DecadeChart({ decadeDistribution = {} }) {
  const data = Object.entries(decadeDistribution)
    .map(([decade, count]) => ({ decade, count }))
    .sort((a, b) => a.decade.localeCompare(b.decade))

  if (data.length === 0) return null

  return (
    <div className="bg-surface rounded-xl p-6" role="img" aria-label="Distribuzione brani per decade">
      <h3 className="text-text-secondary text-sm font-medium mb-4">Distribuzione per Decade</h3>
      <ResponsiveContainer width="100%" height={Math.max(160, data.length * 40 + 20)}>
        <BarChart data={data} layout="vertical" margin={{ left: 10, right: 20, top: 5, bottom: 5 }}>
          <XAxis type="number" hide />
          <YAxis
            type="category"
            dataKey="decade"
            tick={{ fill: '#b3b3b3', fontSize: 12 }}
            width={50}
            axisLine={false}
            tickLine={false}
          />
          <Tooltip
            contentStyle={TOOLTIP_STYLE.contentStyle}
            labelStyle={TOOLTIP_STYLE.labelStyle}
            formatter={(value) => [`${value} brani`, 'Brani']}
          />
          <Bar dataKey="count" radius={[0, 6, 6, 0]} maxBarSize={24}>
            {data.map((_, index) => (
              <Cell key={index} fill={`rgba(99, 102, 241, ${0.5 + (index / data.length) * 0.5})`} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  )
}
