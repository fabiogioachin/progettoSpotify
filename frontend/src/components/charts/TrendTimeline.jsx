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

export default function TrendTimeline({ trends, dailyMinutes, title = 'Trend Temporale', loading = false, temporalRange }) {
  if (loading) {
    return (
      <div className="glow-card bg-surface rounded-xl p-5 animate-pulse">
        <div className="h-5 bg-surface-hover rounded w-32 mb-4" />
        <div className="h-[300px] bg-surface-hover rounded" />
      </div>
    )
  }

  if (!trends || trends.length === 0) {
    return null
  }

  // Controlla se le features audio sono disponibili (non tutte zero)
  const hasFeatures = trends.some((t) =>
    t.features && Object.entries(t.features).some(([k, v]) => k !== 'tempo' && v && v > 0)
  )

  if (hasFeatures) {
    return <FeatureTrend trends={trends} title={title} />
  }

  // Fallback: mostra tempo di ascolto giornaliero
  return <ListeningTimeTrend dailyMinutes={dailyMinutes} temporalRange={temporalRange} />
}

function FeatureTrend({ trends, title }) {
  const data = trends.map((t) => ({
    name: t.label,
    ...t.features,
  }))

  // Filter out feature keys that have all-zero/null values across every period
  const activeKeys = Object.keys(FEATURE_LABELS).filter((key) =>
    trends.some((t) => t.features?.[key] != null && t.features[key] > 0)
  )

  return (
    <div className="glow-card bg-surface rounded-xl p-5">
      <h3 className="text-text-primary font-display font-semibold mb-4">{title}</h3>
      <ResponsiveContainer width="100%" height={300}>
        <AreaChart data={data} margin={{ top: 5, right: 20, left: 0, bottom: 5 }}>
          <defs>
            {activeKeys.map((key) => (
              <linearGradient key={key} id={`gradient-${key}`} x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor={FEATURE_COLORS[key]} stopOpacity={0.3} />
                <stop offset="95%" stopColor={FEATURE_COLORS[key]} stopOpacity={0} />
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
          {activeKeys.map((key) => (
            <Area
              key={key}
              type="monotone"
              dataKey={key}
              stroke={FEATURE_COLORS[key]}
              fill={`url(#gradient-${key})`}
              strokeWidth={2}
              animationDuration={1500}
              connectNulls
            />
          ))}
        </AreaChart>
      </ResponsiveContainer>
    </div>
  )
}

function ListeningTimeTrend({ dailyMinutes, temporalRange }) {
  if (!dailyMinutes || dailyMinutes.length === 0) {
    return null
  }

  const data = dailyMinutes.map((d) => ({
    date: new Date(d.date).toLocaleDateString('it-IT', { day: '2-digit', month: '2-digit' }),
    minuti: d.minutes,
    ascolti: d.plays,
  }))

  const rangeLabel = { '7d': 'ultimi 7 giorni', '30d': 'ultimi 30 giorni', '90d': 'ultimi 3 mesi', 'all': 'tutto lo storico' }

  return (
    <div className="glow-card bg-surface rounded-xl p-5">
      <h3 className="text-text-primary font-display font-semibold mb-1">Tempo di Ascolto</h3>
      <p className="text-text-muted text-xs mb-4">
        Minuti ascoltati al giorno — {rangeLabel[temporalRange] || 'ultimi 30 giorni'}
      </p>
      <ResponsiveContainer width="100%" height={300}>
        <AreaChart data={data} margin={{ top: 5, right: 20, left: 0, bottom: 5 }}>
          <defs>
            <linearGradient id="gradient-listening" x1="0" y1="0" x2="0" y2="1">
              <stop offset="5%" stopColor="#6366f1" stopOpacity={0.4} />
              <stop offset="95%" stopColor="#6366f1" stopOpacity={0} />
            </linearGradient>
          </defs>
          <CartesianGrid strokeDasharray="3 3" stroke={GRID_COLOR} />
          <XAxis
            dataKey="date"
            tick={{ fill: '#b3b3b3', fontSize: 11 }}
            axisLine={{ stroke: GRID_COLOR }}
            interval="preserveStartEnd"
          />
          <YAxis
            tick={{ fill: '#b3b3b3', fontSize: 12 }}
            axisLine={{ stroke: GRID_COLOR }}
            tickFormatter={(v) => `${Math.round(v)} min`}
          />
          <Tooltip
            {...TOOLTIP_STYLE}
            formatter={(val, name) => {
              if (name === 'minuti') return [`${val} min`, 'Tempo']
              return [val, 'Ascolti']
            }}
          />
          <Area
            type="monotone"
            dataKey="minuti"
            stroke="#6366f1"
            fill="url(#gradient-listening)"
            strokeWidth={2}
            animationDuration={1500}
            connectNulls
          />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  )
}
