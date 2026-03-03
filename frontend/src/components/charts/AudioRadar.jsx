import {
  PolarAngleAxis,
  PolarGrid,
  PolarRadiusAxis,
  Radar,
  RadarChart,
  ResponsiveContainer,
  Tooltip,
} from 'recharts'
import { RADAR_LABELS, TOOLTIP_STYLE } from '../../lib/chartTheme'

export default function AudioRadar({ features, title = 'Profilo Audio', loading = false }) {
  if (loading) {
    return (
      <div className="glow-card bg-surface rounded-xl p-5 animate-pulse">
        <div className="h-5 bg-surface-hover rounded w-32 mb-4" />
        <div className="h-[300px] bg-surface-hover rounded" />
      </div>
    )
  }

  if (!features || Object.keys(features).length === 0) {
    return <EmptyState />
  }

  const data = Object.entries(RADAR_LABELS).map(([key, label]) => ({
    feature: label,
    value: Math.round((features[key] ?? 0) * 100),
  }))

  return (
    <div className="glow-card bg-surface rounded-xl p-5">
      <h3 className="text-text-primary font-display font-semibold mb-4">{title}</h3>
      <ResponsiveContainer width="100%" height={300}>
        <RadarChart data={data} cx="50%" cy="50%" outerRadius="75%">
          <PolarGrid
            stroke="#282828"
            strokeDasharray="3 3"
          />
          <PolarAngleAxis
            dataKey="feature"
            tick={{ fill: '#b3b3b3', fontSize: 12 }}
          />
          <PolarRadiusAxis
            angle={30}
            domain={[0, 100]}
            tick={false}
            axisLine={false}
          />
          <Radar
            name="Profilo"
            dataKey="value"
            stroke="#6366f1"
            fill="#6366f1"
            fillOpacity={0.2}
            strokeWidth={2}
            animationDuration={1500}
          />
          <Tooltip
            {...TOOLTIP_STYLE}
            formatter={(val) => [`${val}%`, 'Valore']}
          />
        </RadarChart>
      </ResponsiveContainer>
    </div>
  )
}

function EmptyState() {
  return (
    <div className="glow-card bg-surface rounded-xl p-5 flex items-center justify-center h-[380px]">
      <p className="text-text-muted text-sm">Nessun dato disponibile</p>
    </div>
  )
}
