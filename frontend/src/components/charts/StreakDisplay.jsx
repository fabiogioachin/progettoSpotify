import { motion } from 'framer-motion'
import { Flame, Star, Trophy, Award, Crown } from 'lucide-react'

const DAY_LABELS = ['Lun', 'Mar', 'Mer', 'Gio', 'Ven', 'Sab', 'Dom']

const MILESTONES = [
  { days: 3, icon: Star, label: '3 giorni' },
  { days: 7, icon: Trophy, label: '7 giorni' },
  { days: 14, icon: Award, label: '14 giorni' },
  { days: 30, icon: Crown, label: '30 giorni' },
]

export default function StreakDisplay({ streak = 0, uniqueDays = 0, activeDays = [] }) {
  const progressPct = Math.min((streak / 30) * 100, 100)

  // SVG circle math for progress ring
  const ringSize = 120
  const strokeWidth = 8
  const radius = (ringSize - strokeWidth) / 2
  const circumference = 2 * Math.PI * radius
  const dashOffset = circumference - (progressPct / 100) * circumference

  return (
    <motion.div
      className="glow-card bg-surface rounded-xl p-6"
      style={{ '--circumference': circumference }}
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3 }}
    >

      {/* Header */}
      <div className="flex items-center gap-2 mb-6">
        <Flame size={20} className="text-amber-400" />
        <h3 className="text-text-primary font-display font-semibold text-lg">Streak di Ascolto</h3>
      </div>

      {/* Center: Flame + Progress Ring */}
      <div className="flex flex-col items-center gap-6 mb-8">
        {/* Animated flame with streak number */}
        <div className="relative flex items-center justify-center">
          <svg
            className="flame-animated"
            width="100"
            height="120"
            viewBox="0 0 100 120"
            fill="none"
            xmlns="http://www.w3.org/2000/svg"
          >
            <defs>
              <linearGradient id="flameGradient" x1="50" y1="120" x2="50" y2="0" gradientUnits="userSpaceOnUse">
                <stop offset="0%" stopColor="#f59e0b" />
                <stop offset="50%" stopColor="#f97316" />
                <stop offset="100%" stopColor="#ef4444" />
              </linearGradient>
              <linearGradient id="flameInner" x1="50" y1="120" x2="50" y2="30" gradientUnits="userSpaceOnUse">
                <stop offset="0%" stopColor="#fbbf24" />
                <stop offset="100%" stopColor="#f59e0b" />
              </linearGradient>
            </defs>
            {/* Outer flame */}
            <path
              d="M50 5 C50 5, 15 45, 15 75 C15 100, 30 115, 50 115 C70 115, 85 100, 85 75 C85 45, 50 5, 50 5Z"
              fill="url(#flameGradient)"
              opacity="0.9"
            />
            {/* Inner flame */}
            <path
              d="M50 35 C50 35, 30 60, 30 80 C30 98, 38 110, 50 110 C62 110, 70 98, 70 80 C70 60, 50 35, 50 35Z"
              fill="url(#flameInner)"
              opacity="0.8"
            />
          </svg>
          {/* Streak number overlaid */}
          <span className="absolute text-white text-5xl font-display font-bold" style={{ top: '50%', transform: 'translateY(-30%)' }}>
            {streak}
          </span>
        </div>
        <p className="text-text-secondary text-sm -mt-2">giorni consecutivi</p>

        {/* Progress ring */}
        <div className="relative">
          <svg width={ringSize} height={ringSize} className="-rotate-90">
            {/* Background track */}
            <circle
              cx={ringSize / 2}
              cy={ringSize / 2}
              r={radius}
              fill="none"
              stroke="#282828"
              strokeWidth={strokeWidth}
            />
            {/* Progress arc */}
            <circle
              className="progress-ring-circle"
              cx={ringSize / 2}
              cy={ringSize / 2}
              r={radius}
              fill="none"
              stroke="#6366f1"
              strokeWidth={strokeWidth}
              strokeLinecap="round"
              strokeDasharray={circumference}
              strokeDashoffset={dashOffset}
            />
          </svg>
          {/* Center text */}
          <div className="absolute inset-0 flex flex-col items-center justify-center">
            <span className="text-text-primary font-display font-bold text-2xl">{streak}</span>
            <span className="text-text-muted text-[10px]">/ 30 giorni</span>
          </div>
        </div>

        {/* Unique days stat */}
        <p className="text-text-secondary text-sm">
          <span className="text-text-primary font-semibold">{uniqueDays}</span> giorni unici di ascolto
        </p>
      </div>

      {/* Mini week calendar */}
      <div className="mb-8">
        <p className="text-text-muted text-xs uppercase tracking-wide mb-3 text-center">Ultimi 7 giorni</p>
        <div className="flex justify-center gap-3">
          {DAY_LABELS.map((day, i) => {
            const isActive = activeDays[i] ?? false
            return (
              <div key={i} className="flex flex-col items-center gap-1.5">
                <div
                  className={`w-9 h-9 rounded-full flex items-center justify-center transition-all duration-300 ${
                    isActive
                      ? 'bg-accent text-white'
                      : 'border-2 border-surface-hover text-text-muted'
                  }`}
                >
                  {isActive && (
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round">
                      <polyline points="20 6 9 17 4 12" />
                    </svg>
                  )}
                </div>
                <span className={`text-[10px] ${isActive ? 'text-text-secondary' : 'text-text-muted'}`}>
                  {day}
                </span>
              </div>
            )
          })}
        </div>
      </div>

      {/* Milestone badges */}
      <div>
        <p className="text-text-muted text-xs uppercase tracking-wide mb-3 text-center">Traguardi</p>
        <div className="flex justify-center gap-4">
          {MILESTONES.map(({ days, icon: Icon, label }) => {
            const achieved = streak >= days
            return (
              <div key={days} className="flex flex-col items-center gap-1.5">
                <div
                  className={`w-12 h-12 rounded-xl flex items-center justify-center transition-all duration-300 ${
                    achieved
                      ? 'bg-accent/10 text-accent'
                      : 'bg-surface-hover text-text-muted'
                  }`}
                >
                  <Icon size={22} />
                </div>
                <span className={`text-[10px] ${achieved ? 'text-text-secondary' : 'text-text-muted'}`}>
                  {label}
                </span>
              </div>
            )
          })}
        </div>
      </div>
    </motion.div>
  )
}
