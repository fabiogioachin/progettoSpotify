import { motion } from 'framer-motion'

function formatHour(h) {
  return String(h).padStart(2, '0') + ':00'
}

export default function SlidePeakHours({ data }) {
  const temporal = data?.temporal
  const peakHours = temporal?.peak_hours?.slice(0, 3) || []
  const patterns = temporal?.patterns
  const weekdayPct = patterns?.weekday_pct ?? 50
  const weekendPct = 100 - weekdayPct

  if (!peakHours.length) return null

  return (
    <div className="flex flex-col items-center justify-center min-h-[100dvh] px-6 py-16 relative">
      <motion.h2
        className="text-3xl font-display font-bold text-text-primary mb-10"
        initial={{ opacity: 0, y: -20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.4 }}
      >
        Quando Ascolti
      </motion.h2>

      {peakHours.length > 0 ? (
        <>
          {/* Peak hours */}
          <div className="flex gap-6 mb-12">
            {peakHours.map((ph, i) => (
              <motion.div
                key={ph.hour}
                className="flex flex-col items-center"
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.4, delay: 0.15 * i }}
              >
                <span className="text-4xl font-display font-bold text-accent">
                  {formatHour(ph.hour)}
                </span>
                <span className="text-sm text-text-secondary mt-1">
                  {ph.count} ascolti
                </span>
              </motion.div>
            ))}
          </div>

          {/* Weekday/Weekend bar */}
          {patterns && (
            <motion.div
              className="w-full max-w-sm"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              transition={{ duration: 0.4, delay: 0.5 }}
            >
              <div className="flex justify-between text-sm text-text-secondary mb-2">
                <span>Feriali {Math.round(weekdayPct)}%</span>
                <span>Weekend {Math.round(weekendPct)}%</span>
              </div>
              <div className="flex h-3 rounded-full overflow-hidden bg-surface">
                <motion.div
                  className="bg-accent rounded-l-full"
                  initial={{ width: 0 }}
                  animate={{ width: `${weekdayPct}%` }}
                  transition={{ duration: 0.6, delay: 0.6 }}
                />
                <motion.div
                  className="bg-accent-hover rounded-r-full"
                  initial={{ width: 0 }}
                  animate={{ width: `${weekendPct}%` }}
                  transition={{ duration: 0.6, delay: 0.7 }}
                />
              </div>
            </motion.div>
          )}
        </>
      ) : null}
    </div>
  )
}
