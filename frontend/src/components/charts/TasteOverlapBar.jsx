import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Cell } from 'recharts'
import { TOOLTIP_STYLE } from '../../lib/chartTheme'

const OVERLAP_COLORS = ['#6a6a6a', '#6366f1', '#1DB954']

export default function TasteOverlapBar({ data = [], title = 'Distribuzione Artisti per Periodo', loading = false }) {
  if (loading) {
    return (
      <div className="glow-card bg-surface rounded-xl p-5">
        <h3 className="text-text-primary font-display font-semibold mb-4">{title}</h3>
        <div className="h-48 flex items-center justify-center">
          <div className="w-8 h-8 border-2 border-accent border-t-transparent rounded-full animate-spin" />
        </div>
      </div>
    )
  }

  if (!data.length) {
    return (
      <div className="glow-card bg-surface rounded-xl p-5">
        <h3 className="text-text-primary font-display font-semibold mb-4">{title}</h3>
        <p className="text-text-muted text-sm text-center py-8">Nessun dato disponibile</p>
      </div>
    )
  }

  return (
    <div className="glow-card bg-surface rounded-xl p-5">
      <h3 className="text-text-primary font-display font-semibold mb-4">{title}</h3>
      <ResponsiveContainer width="100%" height={200}>
        <BarChart data={data} layout="vertical" margin={{ top: 5, right: 20, left: 20, bottom: 5 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#282828" horizontal={false} />
          <XAxis type="number" tick={{ fill: '#b3b3b3', fontSize: 12 }} />
          <YAxis type="category" dataKey="label" tick={{ fill: '#b3b3b3', fontSize: 12 }} width={80} />
          <Tooltip {...TOOLTIP_STYLE} formatter={(value) => [`${value} artisti`, 'Conteggio']} />
          <Bar dataKey="count" radius={[0, 4, 4, 0]} animationDuration={1500}>
            {data.map((entry, index) => (
              <Cell key={`cell-${index}`} fill={OVERLAP_COLORS[index % OVERLAP_COLORS.length]} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  )
}
