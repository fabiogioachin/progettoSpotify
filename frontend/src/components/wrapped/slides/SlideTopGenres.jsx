import { motion } from 'framer-motion'

function capitalize(s) {
  return s ? s.charAt(0).toUpperCase() + s.slice(1) : ''
}

export default function SlideTopGenres({ data }) {
  const genres = data?.profile?.genres
  if (!genres || typeof genres !== 'object') return null

  const sorted = Object.entries(genres)
    .sort((a, b) => b[1] - a[1])
    .slice(0, 5)

  if (!sorted.length) return null

  const maxPct = sorted[0]?.[1] || 1

  return (
    <div className="flex flex-col items-center justify-center min-h-[100dvh] px-6 py-16 relative">
      <motion.h2
        className="text-3xl font-display font-bold text-text-primary mb-10"
        initial={{ opacity: 0, y: -20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.4 }}
      >
        I Tuoi Generi
      </motion.h2>

      <div className="w-full max-w-md space-y-5">
        {sorted.map(([genre, pct], i) => {
          const widthPct = Math.round((pct / maxPct) * 100)

          return (
            <motion.div
              key={genre}
              initial={{ opacity: 0, x: -20 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ duration: 0.3, delay: 0.1 * i }}
            >
              <div className="flex justify-between mb-1">
                <span className="text-sm text-text-primary font-medium">
                  {capitalize(genre)}
                </span>
                <span className="text-sm text-text-secondary">
                  {Math.round(pct)}%
                </span>
              </div>
              <div className="h-3 bg-surface rounded-full overflow-hidden">
                <motion.div
                  className="h-full bg-accent rounded-full"
                  initial={{ width: 0 }}
                  animate={{ width: `${widthPct}%` }}
                  transition={{ duration: 0.6, delay: 0.1 * i + 0.2 }}
                />
              </div>
            </motion.div>
          )
        })}
      </div>
    </div>
  )
}
