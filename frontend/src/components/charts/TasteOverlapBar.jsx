import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Cell } from 'recharts'

const OVERLAP_COLORS = ['#6a6a6a', '#6366f1', '#1DB954']

const OVERLAP_DESCRIPTIONS = {
  'Passeggeri': 'Artisti che compaiono solo in un periodo — gusti del momento',
  'Consolidati': 'Artisti presenti in due periodi — si stanno radicando nei tuoi ascolti',
  'Fedelissimi': 'Artisti presenti in tutti e tre i periodi — il cuore del tuo gusto musicale',
}

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
    return null
  }

  const total = data.reduce((sum, d) => sum + d.count, 0)

  return (
    <div className="glow-card bg-surface rounded-xl p-5">
      <h3 className="text-text-primary font-display font-semibold mb-1">{title}</h3>
      <p className="text-text-muted text-xs mb-4">
        In quanti periodi (ultimo mese, 6 mesi, sempre) compaiono i tuoi artisti
      </p>
      <ResponsiveContainer width="100%" height={200}>
        <BarChart data={data} layout="vertical" margin={{ top: 5, right: 20, left: 20, bottom: 5 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#282828" horizontal={false} />
          <XAxis type="number" tick={{ fill: '#b3b3b3', fontSize: 12 }} />
          <YAxis type="category" dataKey="label" tick={{ fill: '#b3b3b3', fontSize: 12 }} width={80} />
          <Tooltip
            content={({ active, payload }) => {
              if (!active || !payload?.length) return null
              const { label, count } = payload[0].payload
              const pct = total > 0 ? Math.round((count / total) * 100) : 0
              return (
                <div className="bg-surface-hover border border-border rounded-lg p-3 shadow-xl text-sm max-w-[280px]">
                  <p className="text-text-primary font-medium">{label}</p>
                  <p className="text-accent text-lg font-bold">{count} artisti ({pct}%)</p>
                  <p className="text-text-muted text-xs mt-1">
                    {OVERLAP_DESCRIPTIONS[label] || ''}
                  </p>
                </div>
              )
            }}
          />
          <Bar dataKey="count" radius={[0, 4, 4, 0]} animationDuration={1500}>
            {data.map((entry, index) => (
              <Cell key={`cell-${index}`} fill={OVERLAP_COLORS[index % OVERLAP_COLORS.length]} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
      {/* Legend inline */}
      <div className="flex flex-wrap gap-4 mt-3">
        {data.map((d, i) => (
          <div key={d.label} className="flex items-center gap-2">
            <div className="w-3 h-3 rounded-sm" style={{ backgroundColor: OVERLAP_COLORS[i % OVERLAP_COLORS.length] }} />
            <span className="text-text-muted text-xs">{d.label}: {d.count} artisti</span>
          </div>
        ))}
      </div>
    </div>
  )
}
