import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { motion } from 'framer-motion'
import { useSpotifyData } from '../hooks/useSpotifyData'
import WrappedStories from '../components/wrapped/WrappedStories'

export default function WrappedPage() {
  const navigate = useNavigate()
  const [period, setPeriod] = useState('medium_term')
  const { data, loading, error } = useSpotifyData('/api/v1/wrapped', { time_range: period })

  if (loading) {
    return (
      <div className="min-h-[100dvh] bg-background flex flex-col items-center justify-center">
        <motion.p
          className="gradient-text text-2xl font-display font-bold"
          animate={{ opacity: [0.5, 1, 0.5] }}
          transition={{ duration: 2, repeat: Infinity, ease: 'easeInOut' }}
        >
          Preparando il tuo Wrapped...
        </motion.p>
      </div>
    )
  }

  if (error) {
    return (
      <div className="min-h-[100dvh] bg-background flex flex-col items-center justify-center gap-4">
        <p className="text-text-secondary">{error}</p>
        <button
          onClick={() => window.location.reload()}
          className="px-5 py-2.5 bg-accent hover:bg-accent-hover text-white rounded-lg font-medium text-sm transition-colors"
        >
          Riprova
        </button>
      </div>
    )
  }

  if (!data) return null

  return (
    <WrappedStories
      data={data}
      period={period}
      onPeriodChange={setPeriod}
      onClose={() => navigate('/dashboard')}
    />
  )
}
