import {
  Area,
  AreaChart,
  Bar,
  BarChart,
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

  // Controlla se le features audio sono disponibili (non tutte zero)
  const hasFeatures = trends.some((t) =>
    t.features && Object.entries(t.features).some(([k, v]) => k !== 'tempo' && v && v > 0)
  )

  if (hasFeatures) {
    return <FeatureTrend trends={trends} title={title} />
  }

  // Fallback: mostra popolarita' e artisti unici per periodo
  return <PopularityTrend trends={trends} title={title} />
}

function FeatureTrend({ trends, title }) {
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

function PopularityTrend({ trends, title }) {
  const data = trends.map((t) => ({
    name: t.label,
    popularity: t.popularity_avg || 0,
    artists: t.unique_artists || 0,
    tracks: t.track_count || 0,
  }))

  const COLORS = {
    popularity: '#6366f1',
    artists: '#1DB954',
    tracks: '#f59e0b',
  }

  const LABELS = {
    popularity: 'Popolarità media',
    artists: 'Artisti unici',
    tracks: 'Brani analizzati',
  }

  return (
    <div className="glow-card bg-surface rounded-xl p-5">
      <h3 className="text-text-primary font-display font-semibold mb-1">{title}</h3>
      <p className="text-text-muted text-xs mb-4">
        Confronto tra periodi — popolarità, artisti e brani
      </p>
      <ResponsiveContainer width="100%" height={300}>
        <BarChart data={data} margin={{ top: 5, right: 20, left: 0, bottom: 5 }}>
          <CartesianGrid strokeDasharray="3 3" stroke={GRID_COLOR} />
          <XAxis
            dataKey="name"
            tick={{ fill: '#b3b3b3', fontSize: 12 }}
            axisLine={{ stroke: GRID_COLOR }}
          />
          <YAxis
            tick={{ fill: '#b3b3b3', fontSize: 12 }}
            axisLine={{ stroke: GRID_COLOR }}
          />
          <Tooltip
            {...TOOLTIP_STYLE}
            formatter={(val, name) => [val, LABELS[name] || name]}
          />
          <Legend
            formatter={(val) => LABELS[val] || val}
            wrapperStyle={{ color: '#b3b3b3', fontSize: 12 }}
          />
          <Bar dataKey="popularity" fill={COLORS.popularity} radius={[4, 4, 0, 0]} animationDuration={1500} />
          <Bar dataKey="artists" fill={COLORS.artists} radius={[4, 4, 0, 0]} animationDuration={1500} />
          <Bar dataKey="tracks" fill={COLORS.tracks} radius={[4, 4, 0, 0]} animationDuration={1500} />
        </BarChart>
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
