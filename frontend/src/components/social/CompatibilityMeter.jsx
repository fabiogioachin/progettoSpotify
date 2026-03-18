import { useEffect, useState } from 'react'
import { motion } from 'framer-motion'

const RADIUS = 54
const CIRCUMFERENCE = 2 * Math.PI * RADIUS

function MiniBar({ label, value }) {
  return (
    <div className="flex-1 text-center">
      <p className="text-text-muted text-[10px] font-body uppercase tracking-wide mb-1">{label}</p>
      <div className="h-1.5 bg-surface-hover rounded-full overflow-hidden">
        <motion.div
          className="h-full rounded-full"
          style={{ backgroundColor: 'var(--color-accent)' }}
          initial={{ width: 0 }}
          animate={{ width: `${value ?? 0}%` }}
          transition={{ duration: 0.8, ease: 'easeOut', delay: 0.5 }}
        />
      </div>
      <p className="text-text-secondary text-xs font-display mt-1">{value ?? 0}</p>
    </div>
  )
}

export default function CompatibilityMeter({ score, genreScore, artistScore, popularityScore }) {
  const [displayScore, setDisplayScore] = useState(0)

  useEffect(() => {
    if (score === null || score === undefined) return
    let frame
    const start = performance.now()
    const duration = 1200

    function tick(now) {
      const elapsed = now - start
      const progress = Math.min(elapsed / duration, 1)
      // ease out cubic
      const eased = 1 - Math.pow(1 - progress, 3)
      setDisplayScore(Math.round(eased * score))
      if (progress < 1) {
        frame = requestAnimationFrame(tick)
      }
    }

    frame = requestAnimationFrame(tick)
    return () => cancelAnimationFrame(frame)
  }, [score])

  if (score === null || score === undefined) return null

  const offset = CIRCUMFERENCE - (displayScore / 100) * CIRCUMFERENCE

  return (
    <div className="flex flex-col items-center gap-4">
      {/* Circular gauge */}
      <div className="relative w-32 h-32">
        <svg className="w-full h-full -rotate-90" viewBox="0 0 128 128">
          {/* Background circle */}
          <circle
            cx="64"
            cy="64"
            r={RADIUS}
            fill="none"
            stroke="currentColor"
            className="text-surface-hover"
            strokeWidth="8"
          />
          {/* Score arc */}
          <motion.circle
            cx="64"
            cy="64"
            r={RADIUS}
            fill="none"
            stroke="var(--color-accent)"
            strokeWidth="8"
            strokeLinecap="round"
            strokeDasharray={CIRCUMFERENCE}
            initial={{ strokeDashoffset: CIRCUMFERENCE }}
            animate={{ strokeDashoffset: offset }}
            transition={{ duration: 1.2, ease: 'easeOut' }}
          />
        </svg>
        {/* Center text */}
        <div className="absolute inset-0 flex flex-col items-center justify-center">
          <span className="text-3xl font-display text-text-primary">{displayScore}</span>
          <span className="text-[10px] text-text-muted uppercase tracking-wide">/ 100</span>
        </div>
      </div>

      {/* Mini bars */}
      <div className="flex gap-4 w-full max-w-xs">
        <MiniBar label="Generi" value={genreScore != null ? Math.round(genreScore * 100) : null} />
        <MiniBar label="Artisti" value={artistScore != null ? Math.round(artistScore * 100) : null} />
        <MiniBar label="Popolarità" value={popularityScore != null ? Math.round(popularityScore * 100) : null} />
      </div>
    </div>
  )
}
