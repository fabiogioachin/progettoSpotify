import { ResponsiveContainer, PieChart, Pie, Cell, Tooltip } from 'recharts'
import { TOOLTIP_STYLE } from '../../lib/chartTheme'

const GENRE_COLORS = [
  '#6366f1', '#818cf8', '#a5b4fc',
  '#10b981', '#34d399', '#6ee7b7',
  '#f59e0b', '#fbbf24', '#fcd34d',
  '#ec4899', '#f472b6', '#f9a8d4',
  '#06b6d4', '#22d3ee', '#67e8f9',
]

const CustomTooltip = ({ active, payload }) => {
  if (!active || !payload?.length) return null
  const { name, value } = payload[0].payload
  return (
    <div style={{
      ...TOOLTIP_STYLE.contentStyle,
      padding: '8px 12px',
    }}>
      <span style={{ color: '#b3b3b3', fontWeight: 600 }}>{name}</span>
      <span style={{ color: '#FFFFFF', marginLeft: 8 }}>{value}%</span>
    </div>
  )
}

export default function GenreTreemap({ genres, title = 'Distribuzione Generi', loading = false }) {
  if (loading) {
    return (
      <div className="glow-card bg-surface rounded-xl p-5 animate-pulse">
        <div className="h-5 bg-surface-hover rounded w-32 mb-4" />
        <div className="h-[300px] bg-surface-hover rounded" />
      </div>
    )
  }

  if (!genres || Object.keys(genres).length === 0) {
    return null
  }

  const data = Object.entries(genres)
    .slice(0, 12)
    .map(([name, value], idx) => ({
      name,
      value,
      fill: GENRE_COLORS[idx % GENRE_COLORS.length],
    }))

  return (
    <div className="glow-card bg-surface rounded-xl p-5">
      <h3 className="text-text-primary font-display font-semibold mb-4">{title}</h3>
      <div className="flex items-center gap-4">
        <div className="flex-1 min-w-0" style={{ minHeight: 260 }}>
          <ResponsiveContainer width="100%" height={260}>
            <PieChart>
              <Pie
                data={data}
                dataKey="value"
                nameKey="name"
                cx="50%"
                cy="50%"
                innerRadius="45%"
                outerRadius="80%"
                paddingAngle={2}
                animationDuration={1200}
                stroke="none"
              >
                {data.map((entry, idx) => (
                  <Cell key={`cell-${idx}`} fill={entry.fill} />
                ))}
              </Pie>
              <Tooltip content={<CustomTooltip />} />
            </PieChart>
          </ResponsiveContainer>
        </div>
        <div className="flex flex-col gap-1.5 shrink-0 max-h-[260px] overflow-y-auto pr-1">
          {data.map((entry, idx) => (
            <div key={idx} className="flex items-center gap-2 text-sm">
              <span
                className="inline-block w-3 h-3 rounded-sm shrink-0"
                style={{ backgroundColor: entry.fill }}
              />
              <span className="text-text-secondary truncate max-w-[120px]">{entry.name}</span>
              <span className="text-text-muted ml-auto tabular-nums">{entry.value}%</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
