import { useState } from 'react'
import { useAnimatedValue } from '../../hooks/useAnimatedValue'

export default function KPICard({ title, value, suffix = '', trend, icon: Icon, delay = 0, tooltip }) {
  const [showTooltip, setShowTooltip] = useState(false)
  const animatedValue = useAnimatedValue(
    typeof value === 'number' ? value : null,
    1200,
    value % 1 !== 0 ? 1 : 0
  )

  const displayValue = typeof value === 'number' ? animatedValue : value

  return (
    <div
      className="glow-card bg-surface rounded-xl p-5 animate-slide-up relative overflow-hidden"
      style={{ animationDelay: `${delay}ms`, animationFillMode: 'both' }}
      onMouseEnter={() => tooltip && setShowTooltip(true)}
      onMouseLeave={() => setShowTooltip(false)}
    >
      {/* Accent bar */}
      <div className="absolute left-0 top-0 bottom-0 w-[3px] bg-accent rounded-r-full" />
      <div className="flex items-start justify-between mb-3">
        <span className="text-text-secondary text-sm font-medium">{title}</span>
        {Icon && (
          <div className="w-8 h-8 rounded-lg bg-accent/10 flex items-center justify-center">
            <Icon size={16} className="text-accent" />
          </div>
        )}
      </div>
      <div className="flex items-end gap-2">
        <span className="text-3xl font-display font-bold text-text-primary">
          {displayValue}{suffix}
        </span>
        {trend !== undefined && trend !== null && (
          <span
            className={`text-xs font-medium px-1.5 py-0.5 rounded mb-1
              ${trend >= 0 ? 'text-emerald-400 bg-emerald-400/10' : 'text-red-400 bg-red-400/10'}
            `}
          >
            {trend >= 0 ? '+' : ''}{trend}%
          </span>
        )}
      </div>
      {/* Tooltip on hover */}
      {showTooltip && tooltip && (
        <div className="absolute inset-x-0 bottom-0 bg-surface-hover/95 backdrop-blur-sm border-t border-border px-4 py-2 text-xs text-text-secondary z-10 animate-fade-in">
          {tooltip}
        </div>
      )}
    </div>
  )
}
