import { RadarChart, PolarGrid, PolarAngleAxis, Radar, ResponsiveContainer } from 'recharts'
import { GRID_COLOR } from '../../lib/chartTheme'

function truncateGenre(genre, maxLen = 12) {
  if (!genre) return ''
  return genre.length > maxLen ? genre.slice(0, maxLen) + '...' : genre
}

export default function GenreDNA({ topGenres = [] }) {
  const genres = topGenres.slice(0, 6)
  if (genres.length === 0) return null

  // Build radar data — genres are ranked by frequency (backend returns them sorted)
  // but we don't have exact counts, so use rank-based decay (1st = 100, last ≈ 50)
  const step = genres.length > 1 ? 50 / (genres.length - 1) : 0
  const data = genres.map((genre, i) => ({
    genre: truncateGenre(genre),
    fullName: genre,
    value: Math.round(100 - i * step),
  }))

  return (
    <div className="bg-surface rounded-xl p-6" role="img" aria-label="DNA musicale — generi principali">
      <h3 className="text-text-secondary text-sm font-medium mb-4">DNA Musicale</h3>
      <ResponsiveContainer width="100%" height={260}>
        <RadarChart data={data} cx="50%" cy="50%" outerRadius="70%">
          <PolarGrid stroke={GRID_COLOR} />
          <PolarAngleAxis
            dataKey="genre"
            tick={{ fill: '#b3b3b3', fontSize: 11 }}
          />
          <Radar
            dataKey="value"
            stroke="#6366f1"
            fill="#6366f1"
            fillOpacity={0.3}
            strokeWidth={2}
          />
        </RadarChart>
      </ResponsiveContainer>
    </div>
  )
}
