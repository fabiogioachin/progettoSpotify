import {
  Area,
  AreaChart,
  CartesianGrid,
  Legend,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import { FEATURE_COLORS, TOOLTIP_STYLE, GRID_COLOR } from '../../lib/chartTheme'
import { FEATURE_LABELS } from '../../lib/constants'

export default function TrendTimeline({ trends, title = 'Trend Temporale', loading = false }) {
  if (loading) {
    return (
      <div className="glow-card bg-surface rounded-xl p-5 animate-pulse">
        <div className="h-5 bg-surface-hover rounded w-32 mb-4" />
        <div className="h-[300px] bg-surface-hover rounded" />
      </div>
    )
  }

  if (!trends || trends.length === 0) {
    return <EmptyState />
  }

  const data = trends.map((t) => ({
    name: t.label,
    ...t.features,
  }))

  return (
    <div className="glow-card bg-surface rounded-xl p-5">
      <h3 className="text-text-primary font-display font-semibold mb-4">{title}</h3>
      <ResponsiveContainer width="100%" height={300}>
        <AreaChart data={data} margin={{ top: 5, right: 20, left: 0, bottom: 5 }}>
          <defs>
            {Object.entries(FEATURE_COLORS).map(([key, color]) => (
              <linearGradient key={key} id={`gradient-${key}`} x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor={color} stopOpacity={0.3} />
                <stop offset="95%" stopColor={color} stopOpacity={0} />
              </linearGradient>
            ))}
          </defs>
          <CartesianGrid strokeDasharray="3 3" stroke={GRID_COLOR} />
          <XAxis
            dataKey="name"
            tick={{ fill: '#b3b3b3', fontSize: 12 }}
            axisLine={{ stroke: GRID_COLOR }}
          />
          <YAxis
            domain={[0, 1]}
            tick={{ fill: '#b3b3b3', fontSize: 12 }}
            axisLine={{ stroke: GRID_COLOR }}
            tickFormatter={(v) => `${Math.round(v * 100)}%`}
          />
          <Tooltip
            {...TOOLTIP_STYLE}
            formatter={(val, name) => [
              `${Math.round(val * 100)}%`,
              FEATURE_LABELS[name] || name,
            ]}
          />
          <Legend
            formatter={(val) => FEATURE_LABELS[val] || val}
            wrapperStyle={{ color: '#b3b3b3', fontSize: 12 }}
          />
          {Object.entries(FEATURE_LABELS).map(([key]) => (
            <Area
              key={key}
              type="monotone"
              dataKey={key}
              stroke={FEATURE_COLORS[key]}
              fill={`url(#gradient-${key})`}
              strokeWidth={2}
              animationDuration={1500}
            />
          ))}
        </AreaChart>
      </ResponsiveContainer>
    </div>
  )
}

function EmptyState() {
  return (
    <div className="glow-card bg-surface rounded-xl p-5 flex items-center justify-center h-[380px]">
      <p className="text-text-muted text-sm">Nessun trend disponibile</p>
    </div>
  )
}
