import { RadarChart, PolarGrid, PolarAngleAxis, Radar, ResponsiveContainer } from 'recharts'
import { GRID_COLOR } from '../../lib/chartTheme'

function truncateGenre(genre, maxLen = 12) {
  if (!genre) return ''
  return genre.length > maxLen ? genre.slice(0, maxLen) + '...' : genre
}

export default function GenreDNA({ topGenres = [] }) {
  const genres = topGenres.slice(0, 6)
  if (genres.length === 0) return null

  // Build radar data — each genre gets a fixed value since we're showing presence, not magnitude
  // Using index-based scoring: first genre = highest
  const data = genres.map((genre, i) => ({
    genre: truncateGenre(genre),
    fullName: genre,
    value: 100 - i * 12,
  }))

  return (
    <div className="bg-surface rounded-xl p-6">
      <h3 className="text-text-secondary text-sm font-medium mb-4">DNA Musicale</h3>
      <ResponsiveContainer width="100%" height={260}>
        <RadarChart data={data} cx="50%" cy="50%" outerRadius="70%">
          <PolarGrid stroke={GRID_COLOR} />
          <PolarAngleAxis
            dataKey="genre"
            tick={{ fill: 'var(--text-secondary)', fontSize: 11 }}
          />
          <Radar
            dataKey="value"
            stroke="var(--accent)"
            fill="var(--accent)"
            fillOpacity={0.3}
            strokeWidth={2}
          />
        </RadarChart>
      </ResponsiveContainer>
    </div>
  )
}
