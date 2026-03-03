import {
  Bar,
  BarChart,
  CartesianGrid,
  Legend,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import { PLAYLIST_COLORS, RADAR_LABELS, TOOLTIP_STYLE } from '../../lib/chartTheme'

export default function PlaylistComparison({ comparisons, playlistNames = {}, loading = false }) {
  if (loading) {
    return (
      <div className="glow-card bg-surface rounded-xl p-5 animate-pulse">
        <div className="h-5 bg-surface-hover rounded w-32 mb-4" />
        <div className="h-[300px] bg-surface-hover rounded" />
      </div>
    )
  }

  if (!comparisons || comparisons.length === 0) {
    return <EmptyState />
  }

  // Trasforma dati: una riga per feature, una colonna per playlist
  const features = ['energy', 'valence', 'danceability', 'acousticness', 'instrumentalness']
  const data = features.map((feat) => {
    const row = { feature: RADAR_LABELS[feat] || feat }
    comparisons.forEach((comp, idx) => {
      const name = playlistNames[comp.playlist_id] || `Playlist ${idx + 1}`
      row[name] = Math.round((comp.averages?.[feat] ?? 0) * 100)
    })
    return row
  })

  const barNames = comparisons.map(
    (comp, idx) => playlistNames[comp.playlist_id] || `Playlist ${idx + 1}`
  )

  return (
    <div className="glow-card bg-surface rounded-xl p-5">
      <h3 className="text-text-primary font-display font-semibold mb-4">
        Confronto Audio Features
      </h3>
      <ResponsiveContainer width="100%" height={400}>
        <BarChart data={data} margin={{ top: 5, right: 20, left: 0, bottom: 5 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#282828" />
          <XAxis
            dataKey="feature"
            tick={{ fill: '#b3b3b3', fontSize: 11 }}
            axisLine={{ stroke: '#282828' }}
          />
          <YAxis
            domain={[0, 100]}
            tick={{ fill: '#b3b3b3', fontSize: 12 }}
            axisLine={{ stroke: '#282828' }}
            tickFormatter={(v) => `${v}%`}
          />
          <Tooltip
            {...TOOLTIP_STYLE}
            formatter={(val) => [`${val}%`, '']}
          />
          <Legend wrapperStyle={{ color: '#b3b3b3', fontSize: 12 }} />
          {barNames.map((name, idx) => (
            <Bar
              key={name}
              dataKey={name}
              fill={PLAYLIST_COLORS[idx % PLAYLIST_COLORS.length]}
              radius={[4, 4, 0, 0]}
              animationDuration={1200}
              animationBegin={idx * 200}
            />
          ))}
        </BarChart>
      </ResponsiveContainer>
    </div>
  )
}

function EmptyState() {
  return (
    <div className="glow-card bg-surface rounded-xl p-5 flex items-center justify-center h-[480px]">
      <p className="text-text-muted text-sm">Seleziona almeno 2 playlist per il confronto</p>
    </div>
  )
}
