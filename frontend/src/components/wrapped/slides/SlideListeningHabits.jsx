import { motion } from 'framer-motion'
import { Music, Flame, Clock, Timer } from 'lucide-react'

const stats = [
  { key: 'total_plays', icon: Music, label: 'Ascolti totali' },
  { key: 'max_streak', icon: Flame, label: 'Streak massimo', suffix: ' gg' },
  { key: 'sessions', icon: Clock, label: 'Sessioni' },
  { key: 'avg_duration', icon: Timer, label: 'Durata media', suffix: ' min' },
]

export default function SlideListeningHabits({ data }) {
  const temporal = data?.temporal

  const values = {
    total_plays: temporal?.total_plays || 0,
    max_streak: temporal?.streak?.max_streak || 0,
    sessions: temporal?.sessions?.count || 0,
    avg_duration: temporal?.sessions?.avg_duration_minutes
      ? Math.round(temporal.sessions.avg_duration_minutes)
      : 0,
  }

  if (!values.total_plays && !values.max_streak && !values.sessions && !values.avg_duration) return null

  return (
    <div className="flex flex-col items-center justify-center min-h-[100dvh] px-6 py-16 relative">
      <motion.h2
        className="text-3xl font-display font-bold text-text-primary mb-10"
        initial={{ opacity: 0, y: -20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.4 }}
      >
        Le Tue Abitudini
      </motion.h2>

      <div className="grid grid-cols-2 gap-6 max-w-sm w-full">
        {stats.map((stat, i) => {
          const Icon = stat.icon
          const value = values[stat.key]

          return (
            <motion.div
              key={stat.key}
              className="flex flex-col items-center text-center"
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.4, delay: 0.15 * i }}
            >
              <Icon size={24} className="text-accent mb-2" />
              <span className="text-4xl font-display font-bold text-accent">
                {value}
                {stat.suffix || ''}
              </span>
              <span className="text-sm text-text-secondary mt-1">
                {stat.label}
              </span>
            </motion.div>
          )
        })}
      </div>
    </div>
  )
}
