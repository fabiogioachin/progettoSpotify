import { ScatterChart, Scatter, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Cell } from 'recharts'
import { Map } from 'lucide-react'

const GENRE_COLORS = [
  '#6366f1', '#1DB954', '#f59e0b', '#ec4899', '#06b6d4', '#8b5cf6'
]

export default function TasteMap({ points = [], varianceExplained = [], featureMode, genreGroups = {} }) {
  if (featureMode === 'insufficient' || points.length < 3) {
    return null
  }

  // Build genre -> color mapping from genre_groups (sorted by count desc)
  const topGenres = Object.entries(genreGroups)
    .sort((a, b) => b[1] - a[1])
    .slice(0, 6)
    .map(([genre]) => genre)

  const genreColorMap = {}
  topGenres.forEach((genre, i) => {
    genreColorMap[genre] = GENRE_COLORS[i]
  })

  const getColor = (point) => genreColorMap[point.primary_genre] || '#4b5563'

  const getSize = (point) => {
    const pop = point.popularity || 0
    return Math.max(4, Math.min(12, 4 + (pop / 100) * 8))
  }

  const pc1Var = varianceExplained[0] ? Math.round(varianceExplained[0] * 100) : '?'
  const pc2Var = varianceExplained[1] ? Math.round(varianceExplained[1] * 100) : '?'

  const chartData = points.map(p => ({
    ...p,
    z: getSize(p),
  }))

  return (
    <div className="glow-card bg-surface rounded-xl p-5">
      <h3 className="text-text-primary font-display font-semibold mb-1 flex items-center gap-2">
        <Map size={18} className="text-accent" />
        Mappa del tuo gusto
      </h3>
      {featureMode === 'genre_popularity' && (
        <p className="text-text-muted text-xs mb-3">
          Basato su generi e popolarità. Analizza i brani per una mappa più precisa.
        </p>
      )}
      {featureMode === 'audio' && (
        <p className="text-text-muted text-xs mb-3">
          Basato su generi, popolarità e caratteristiche audio dei tuoi brani.
        </p>
      )}
      <ResponsiveContainer width="100%" height={360}>
        <ScatterChart margin={{ top: 10, right: 20, bottom: 30, left: 10 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#282828" />
          <XAxis
            type="number"
            dataKey="x"
            name={`Componente 1 (${pc1Var}%)`}
            tick={{ fill: '#b3b3b3', fontSize: 11 }}
            axisLine={{ stroke: '#282828' }}
            label={{ value: `Componente 1 (${pc1Var}%)`, position: 'insideBottom', offset: -20, fill: '#8a8a8a', fontSize: 11 }}
          />
          <YAxis
            type="number"
            dataKey="y"
            name={`Componente 2 (${pc2Var}%)`}
            tick={{ fill: '#b3b3b3', fontSize: 11 }}
            axisLine={{ stroke: '#282828' }}
            label={{ value: `Componente 2 (${pc2Var}%)`, angle: -90, position: 'insideLeft', fill: '#8a8a8a', fontSize: 11 }}
          />
          <Tooltip
            content={({ payload }) => {
              if (!payload || !payload.length) return null
              const d = payload[0].payload
              return (
                <div className="bg-surface-hover border border-border rounded-lg px-3 py-2 shadow-lg">
                  <p className="text-text-primary text-sm font-semibold">{d.name}</p>
                  {d.primary_genre && (
                    <p className="text-text-secondary text-xs">{d.primary_genre}</p>
                  )}
                  <p className="text-text-muted text-xs">Pop. {d.popularity}</p>
                </div>
              )
            }}
          />
          <Scatter data={chartData} fill="#6366f1">
            {chartData.map((point, idx) => (
              <Cell
                key={point.id || idx}
                fill={getColor(point)}
                fillOpacity={0.8}
                r={getSize(point)}
              />
            ))}
          </Scatter>
        </ScatterChart>
      </ResponsiveContainer>
      {topGenres.length > 0 && (
        <div className="flex flex-wrap gap-3 mt-3">
          {topGenres.map((genre, i) => (
            <div key={genre} className="flex items-center gap-1.5">
              <div className="w-2.5 h-2.5 rounded-full" style={{ backgroundColor: GENRE_COLORS[i] }} />
              <span className="text-text-muted text-xs">{genre}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
