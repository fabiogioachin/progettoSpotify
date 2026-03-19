import { useEffect, useState, useRef } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { Activity, Clock, AlertTriangle, Timer } from 'lucide-react'

export function ThrottleBanner() {
  const [usage, setUsage] = useState({ current: 0, max: 25, pct: 0 })
  const [countdown, setCountdown] = useState(0)
  const [totalDuration, setTotalDuration] = useState(0)
  const [windowReset, setWindowReset] = useState(0)
  const windowResetRef = useRef(0)

  // Listen for usage updates from API responses
  useEffect(() => {
    const handler = (e) => {
      setUsage(e.detail)
      const reset = e.detail.reset || 0
      setWindowReset(reset)
      windowResetRef.current = reset
    }
    window.addEventListener('api:usage', handler)
    return () => window.removeEventListener('api:usage', handler)
  }, [])

  // Listen for throttle events (429)
  useEffect(() => {
    const handler = (e) => {
      const secs = Math.ceil(e.detail.retryAfter)
      setCountdown(secs)
      setTotalDuration(secs)
    }
    window.addEventListener('api:throttle', handler)
    return () => window.removeEventListener('api:throttle', handler)
  }, [])

  // Countdown tick for 429 throttle
  useEffect(() => {
    if (countdown <= 0) return
    const timer = setInterval(() => {
      setCountdown(prev => prev <= 1 ? 0 : prev - 1)
    }, 1000)
    return () => clearInterval(timer)
  }, [countdown])

  // Rolling countdown for sliding window reset
  useEffect(() => {
    if (windowReset <= 0) return
    const timer = setInterval(() => {
      setWindowReset(prev => {
        const next = prev - 1
        if (next <= 0) {
          windowResetRef.current = 0
          return 0
        }
        windowResetRef.current = next
        return next
      })
    }, 1000)
    return () => clearInterval(timer)
  }, [windowReset > 0]) // eslint-disable-line react-hooks/exhaustive-deps

  // Determine banner state
  const isThrottled = countdown > 0
  const isCritical = !isThrottled && usage.pct > 85
  const isWarning = !isThrottled && !isCritical && usage.pct > 60
  const showAlertBanner = isThrottled || isCritical || isWarning
  const showRollingCountdown = !showAlertBanner && windowReset > 0 && usage.current > 0

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
    <>
      {/* Alert banner (429 / critical / warning) */}
      <AnimatePresence>
        {showAlertBanner && (
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
                <div
                  className="h-full bg-red-400 rounded-full transition-all duration-1000 ease-linear"
                  style={{ width: `${totalDuration > 0 ? (countdown / totalDuration) * 100 : 0}%` }}
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

      {/* Rolling countdown (always visible when API calls are in the sliding window) */}
      <AnimatePresence>
        {showRollingCountdown && (
          <motion.div
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: 10 }}
            transition={{ duration: 0.2 }}
            className="fixed bottom-4 right-4 z-40
                       bg-surface/90 border border-surface-hover backdrop-blur-sm
                       rounded-lg px-3 py-2 flex items-center gap-2
                       text-xs text-text-secondary shadow-md"
          >
            <Timer className="w-3.5 h-3.5 text-accent flex-shrink-0" />
            <span>
              Finestra API: <span className="text-text-primary font-medium">{usage.current}/{usage.max}</span>
              {' '}&bull; rinnovo tra{' '}
              <span className="font-display font-medium text-accent">{Math.ceil(windowReset)}s</span>
            </span>
          </motion.div>
        )}
      </AnimatePresence>
    </>
  )
}
