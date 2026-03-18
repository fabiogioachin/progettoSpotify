import { useEffect, useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { Activity, Clock, AlertTriangle } from 'lucide-react'

export function ThrottleBanner() {
  const [usage, setUsage] = useState({ current: 0, max: 25, pct: 0 })
  const [countdown, setCountdown] = useState(0)

  // Listen for usage updates from API responses
  useEffect(() => {
    const handler = (e) => setUsage(e.detail)
    window.addEventListener('api:usage', handler)
    return () => window.removeEventListener('api:usage', handler)
  }, [])

  // Listen for throttle events (429)
  useEffect(() => {
    const handler = (e) => setCountdown(Math.ceil(e.detail.retryAfter))
    window.addEventListener('api:throttle', handler)
    return () => window.removeEventListener('api:throttle', handler)
  }, [])

  // Countdown tick
  useEffect(() => {
    if (countdown <= 0) return
    const timer = setInterval(() => {
      setCountdown(prev => prev <= 1 ? 0 : prev - 1)
    }, 1000)
    return () => clearInterval(timer)
  }, [countdown])

  // Determine banner state
  const isThrottled = countdown > 0
  const isCritical = !isThrottled && usage.pct > 85
  const isWarning = !isThrottled && !isCritical && usage.pct > 60
  const showBanner = isThrottled || isCritical || isWarning

  // Banner content by state
  let bannerClass, icon, message
  if (isThrottled) {
    bannerClass = 'bg-red-500/15 border-red-500/30 text-red-300'
    icon = <Clock className="w-4 h-4 flex-shrink-0" />
    message = (
      <>
        Limite raggiunto — dati in arrivo tra{' '}
        <span className="font-display font-bold text-red-200">{countdown}s</span>
      </>
    )
  } else if (isCritical) {
    bannerClass = 'bg-red-500/15 border-red-500/30 text-red-300'
    icon = <AlertTriangle className="w-4 h-4 flex-shrink-0" />
    message = (
      <>
        Carico API elevato ({usage.current}/{usage.max}) — rallenta la navigazione
      </>
    )
  } else if (isWarning) {
    bannerClass = 'bg-amber-500/15 border-amber-500/30 text-amber-300'
    icon = <Activity className="w-4 h-4 flex-shrink-0" />
    message = (
      <>
        Carico API moderato ({usage.current}/{usage.max})
      </>
    )
  }

  return (
    <AnimatePresence>
      {showBanner && (
        <motion.div
          initial={{ opacity: 0, y: -20 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0, y: -20 }}
          className={`fixed top-4 left-1/2 -translate-x-1/2 z-50
                     border backdrop-blur-sm
                     rounded-xl px-5 py-3 flex items-center gap-3
                     text-sm shadow-lg ${bannerClass}`}
        >
          {icon}
          <span>{message}</span>
          {/* Progress bar */}
          {isThrottled ? (
            <div className="w-16 h-1.5 bg-red-500/20 rounded-full overflow-hidden">
              <motion.div
                className="h-full bg-red-400 rounded-full"
                initial={{ width: '100%' }}
                animate={{ width: '0%' }}
                transition={{ duration: countdown, ease: 'linear' }}
              />
            </div>
          ) : (
            <div className="w-16 h-1.5 bg-white/10 rounded-full overflow-hidden">
              <div
                className={`h-full rounded-full transition-all duration-500 ${
                  isCritical ? 'bg-red-400' : 'bg-amber-400'
                }`}
                style={{ width: `${usage.pct}%` }}
              />
            </div>
          )}
        </motion.div>
      )}
    </AnimatePresence>
  )
}
