import { useMemo } from 'react'
import { motion } from 'framer-motion'

const RADIUS = 80
const STROKE_WIDTH = 12
const CIRCUMFERENCE = Math.PI * RADIUS // semicircle

function getColor(score) {
  if (score < 30) return '#10b981' // green — mainstream
  if (score < 60) return '#6366f1' // indigo — mid
  return '#a855f7' // purple — obscure
}

function getLabel(score) {
  if (score < 20) return 'Molto mainstream'
  if (score < 40) return 'Tendenzialmente mainstream'
  if (score < 60) return 'Equilibrato'
  if (score < 80) return 'Tendenzialmente oscuro'
  return 'Molto oscuro'
}

export default function ObscurityGauge({ score }) {
  const normalizedScore = Math.max(0, Math.min(100, score ?? 0))
  const offset = CIRCUMFERENCE - (normalizedScore / 100) * CIRCUMFERENCE
  const color = useMemo(() => getColor(normalizedScore), [normalizedScore])
  const label = useMemo(() => getLabel(normalizedScore), [normalizedScore])

  return (
    <div className="bg-surface rounded-xl p-6 flex flex-col items-center">
      <h3 className="text-text-secondary text-sm font-medium mb-4">Indice di Oscurit&agrave;</h3>
      <div className="relative w-[200px] h-[120px]">
        <svg
          viewBox="0 0 200 120"
          className="w-full h-full"
          aria-label={`Indice di oscurit\u00e0: ${normalizedScore}`}
        >
          {/* Background arc */}
          <path
            d="M 20 110 A 80 80 0 0 1 180 110"
            fill="none"
            stroke="#282828"
            strokeWidth={STROKE_WIDTH}
            strokeLinecap="round"
          />
          {/* Filled arc */}
          <motion.path
            d="M 20 110 A 80 80 0 0 1 180 110"
            fill="none"
            stroke={color}
            strokeWidth={STROKE_WIDTH}
            strokeLinecap="round"
            strokeDasharray={CIRCUMFERENCE}
            initial={{ strokeDashoffset: CIRCUMFERENCE }}
            animate={{ strokeDashoffset: offset }}
            transition={{ duration: 1.2, ease: 'easeOut', delay: 0.3 }}
          />
        </svg>
        {/* Center score */}
        <div className="absolute inset-0 flex flex-col items-center justify-end pb-1">
          <span className="text-4xl font-display font-bold text-text-primary">
            {Math.round(normalizedScore)}
          </span>
        </div>
      </div>
      <p className="text-text-muted text-xs mt-2">{label}</p>
    </div>
  )
}
