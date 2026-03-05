import {
  CartesianGrid,
  ResponsiveContainer,
  Scatter,
  ScatterChart,
  Tooltip,
  XAxis,
  YAxis,
  ZAxis,
} from 'recharts'
import { TOOLTIP_STYLE, GRID_COLOR } from '../../lib/chartTheme'

export default function MoodScatter({ tracks, title = 'Mappa Mood: Positività vs Energia', loading = false }) {
  if (loading) {
    return (
      <div className="glow-card bg-surface rounded-xl p-5 animate-pulse">
        <div className="h-5 bg-surface-hover rounded w-32 mb-4" />
        <div className="h-[300px] bg-surface-hover rounded" />
      </div>
    )
  }

  if (!tracks || tracks.length === 0) {
    return null
  }

  const data = tracks
    .filter((t) => t.features)
    .map((t) => ({
      x: Math.round((t.features.valence ?? 0) * 100),
      y: Math.round((t.features.energy ?? 0) * 100),
      z: t.popularity || 50,
      name: t.name,
      artist: t.artist,
    }))

  if (data.length === 0) {
    return null
  }

  return (
    <div className="glow-card bg-surface rounded-xl p-5">
      <h3 className="text-text-primary font-display font-semibold mb-4">{title}</h3>
      <ResponsiveContainer width="100%" height={400}>
        <ScatterChart margin={{ top: 10, right: 20, left: 0, bottom: 10 }}>
          <CartesianGrid strokeDasharray="3 3" stroke={GRID_COLOR} />
          <XAxis
            type="number"
            dataKey="x"
            domain={[0, 100]}
            name="Positività"
            tick={{ fill: '#b3b3b3', fontSize: 12 }}
            axisLine={{ stroke: '#282828' }}
            label={{ value: 'Positività', position: 'bottom', fill: '#6b7280', fontSize: 12 }}
          />
          <YAxis
            type="number"
            dataKey="y"
            domain={[0, 100]}
            name="Energia"
            tick={{ fill: '#b3b3b3', fontSize: 12 }}
            axisLine={{ stroke: '#282828' }}
            label={{ value: 'Energia', angle: -90, position: 'left', fill: '#6b7280', fontSize: 12 }}
          />
          <ZAxis
            type="number"
            dataKey="z"
            range={[30, 200]}
            name="Popolarità"
          />
          <Tooltip
            {...TOOLTIP_STYLE}
            content={<CustomTooltip />}
          />
          {/* Quadranti */}
          <Scatter
            data={data}
            fill="#6366f1"
            fillOpacity={0.7}
            animationDuration={1500}
          />
        </ScatterChart>
      </ResponsiveContainer>

      {/* Legenda quadranti */}
      <div className="grid grid-cols-2 gap-2 mt-3 text-xs text-text-muted">
        <div>😡 Cupo e intenso</div>
        <div className="text-right">🎉 Festivo ed energico</div>
        <div>😢 Triste e calmo</div>
        <div className="text-right">😌 Rilassato e felice</div>
      </div>
    </div>
  )
}

function CustomTooltip({ active, payload }) {
  if (!active || !payload?.length) return null
  const { name, artist, x, y, z } = payload[0].payload

  return (
    <div className="bg-surface-hover border border-border rounded-lg p-3 shadow-xl text-sm">
      <p className="text-text-primary font-medium">{name}</p>
      <p className="text-text-muted text-xs mb-1">{artist}</p>
      <p className="text-text-secondary">Positività: {x}%</p>
      <p className="text-text-secondary">Energia: {y}%</p>
      <p className="text-text-secondary">Popolarità: {z}</p>
    </div>
  )
}

