import { useEffect, useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { Clock } from 'lucide-react'

export function ThrottleBanner() {
  const [countdown, setCountdown] = useState(0)

  useEffect(() => {
    const handler = (e) => {
      setCountdown(Math.ceil(e.detail.retryAfter))
    }
    window.addEventListener('api:throttle', handler)
    return () => window.removeEventListener('api:throttle', handler)
  }, [])

  // Countdown tick
  useEffect(() => {
    if (countdown <= 0) return
    const timer = setInterval(() => {
      setCountdown(prev => {
        if (prev <= 1) return 0
        return prev - 1
      })
    }, 1000)
    return () => clearInterval(timer)
  }, [countdown])

  return (
    <AnimatePresence>
      {countdown > 0 && (
        <motion.div
          initial={{ opacity: 0, y: -20 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0, y: -20 }}
          className="fixed top-4 left-1/2 -translate-x-1/2 z-50
                     bg-amber-500/15 border border-amber-500/30 backdrop-blur-sm
                     rounded-xl px-5 py-3 flex items-center gap-3
                     text-amber-300 text-sm shadow-lg"
        >
          <Clock className="w-4 h-4 flex-shrink-0" />
          <span>
            Carico API elevato — dati in arrivo tra{' '}
            <span className="font-display font-bold text-amber-200">{countdown}s</span>
          </span>
          {/* Progress bar */}
          <div className="w-16 h-1.5 bg-amber-500/20 rounded-full overflow-hidden">
            <motion.div
              className="h-full bg-amber-400 rounded-full"
              initial={{ width: '100%' }}
              animate={{ width: '0%' }}
              transition={{ duration: countdown, ease: 'linear' }}
            />
          </div>
        </motion.div>
      )}
    </AnimatePresence>
  )
}
