export default function ProfileShareCard({ personality, metrics, userName }) {
  if (!personality || !metrics) return null

  const bars = [
    { label: 'Oscurit\u00e0', value: metrics.obscurity_score ?? 0 },
    { label: 'Diversit\u00e0', value: metrics.genre_diversity_index ?? 0 },
    { label: 'Fedelt\u00e0', value: metrics.artist_loyalty_score ?? 0 },
  ]

  const topGenres = (metrics.top_genres || []).slice(0, 3)

  return (
    <div
      className="w-[380px] rounded-2xl overflow-hidden"
      style={{
        background: 'linear-gradient(135deg, #4f46e5, #7c3aed)',
        padding: '32px 28px',
      }}
    >
      {/* Emoji */}
      <div className="text-center mb-2">
        <span className="text-6xl" role="img" aria-label={personality.archetype}>
          {personality.emoji}
        </span>
      </div>

      {/* Archetype */}
      <h2
        className="text-center text-2xl font-bold text-white mb-1"
        style={{ fontFamily: "'Space Grotesk', sans-serif" }}
      >
        {personality.archetype}
      </h2>

      {/* User name */}
      {userName && (
        <p className="text-center text-sm text-white/70 mb-6">{userName}</p>
      )}

      {/* Stat bars */}
      <div className="space-y-3 mb-6">
        {bars.map((bar) => (
          <div key={bar.label}>
            <div className="flex justify-between text-xs text-white/80 mb-1">
              <span>{bar.label}</span>
              <span>{Math.round(bar.value)}</span>
            </div>
            <div className="h-2 bg-white/20 rounded-full overflow-hidden">
              <div
                className="h-full bg-white rounded-full transition-all duration-500"
                style={{ width: `${Math.min(100, bar.value)}%` }}
              />
            </div>
          </div>
        ))}
      </div>

      {/* Top genres */}
      {topGenres.length > 0 && (
        <div className="flex flex-wrap justify-center gap-2 mb-6">
          {topGenres.map((genre) => (
            <span
              key={genre}
              className="text-xs px-3 py-1 rounded-full bg-white/15 text-white/90"
            >
              {genre}
            </span>
          ))}
        </div>
      )}

      {/* Branding */}
      <p className="text-center text-[10px] text-white/40 tracking-widest uppercase">
        Spotify Intelligence
      </p>
    </div>
  )
}
