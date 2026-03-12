import { useState, useRef, useCallback } from 'react'
import { createPortal } from 'react-dom'
import { Link } from 'react-router-dom'
import { motion } from 'framer-motion'
import { useAnimatedValue } from '../../hooks/useAnimatedValue'

export default function KPICard({ title, value, suffix = '', trend, icon: Icon, delay = 0, tooltip, link }) {
  const [showTooltip, setShowTooltip] = useState(false)
  const [mousePos, setMousePos] = useState({ x: 0, y: 0 })
  const hoverTimer = useRef(null)

  const handleMouseEnter = useCallback(() => {
    if (!tooltip) return
    hoverTimer.current = setTimeout(() => setShowTooltip(true), 1000)
  }, [tooltip])

  const handleMouseLeave = useCallback(() => {
    clearTimeout(hoverTimer.current)
    setShowTooltip(false)
  }, [])

  const handleMouseMove = useCallback((e) => {
    if (!tooltip) return
    setMousePos({ x: e.clientX, y: e.clientY })
  }, [tooltip])

  const animatedValue = useAnimatedValue(
    typeof value === 'number' ? value : null,
    1200,
    value % 1 !== 0 ? 1 : 0
  )

  const displayValue = typeof value === 'number' ? animatedValue : value

  const cardContent = (
    <motion.div
      initial={{ opacity: 0, y: 16 }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true, margin: '-40px' }}
      transition={{ duration: 0.4, delay: delay / 1000 }}
      className={`glow-card bg-surface rounded-xl p-5 relative overflow-hidden${link ? ' cursor-pointer hover:ring-1 hover:ring-accent/30 transition-all duration-300' : ''}`}
      onMouseEnter={handleMouseEnter}
      onMouseLeave={handleMouseLeave}
      onMouseMove={handleMouseMove}
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
      {/* Cursor-following tooltip via portal */}
      {showTooltip && tooltip && createPortal(
        <div
          style={{
            position: 'fixed',
            zIndex: 99999,
            left: mousePos.x + 14,
            top: mousePos.y + 14,
            maxWidth: '280px',
            padding: '8px 12px',
            borderRadius: '8px',
            backgroundColor: 'rgba(40, 40, 40, 0.95)',
            backdropFilter: 'blur(8px)',
            border: '1px solid rgba(255, 255, 255, 0.08)',
            color: '#b3b3b3',
            fontSize: '12px',
            lineHeight: '1.4',
            boxShadow: '0 4px 16px rgba(0, 0, 0, 0.4)',
            pointerEvents: 'none',
          }}
        >
          {tooltip}
        </div>,
        document.body
      )}
    </motion.div>
  )

  if (link) {
    return <Link to={link} className="block">{cardContent}</Link>
  }
  return cardContent
}
