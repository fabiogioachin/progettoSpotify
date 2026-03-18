import { useState } from 'react'
import { Trophy } from 'lucide-react'
import { AnimatePresence, motion } from 'framer-motion'
import { StaggerContainer, StaggerItem } from '../ui/StaggerContainer'

const CATEGORIES = [
  { key: 'obscurity', label: 'Oscurit\u00e0' },
  { key: 'plays', label: 'Ascolti' },
  { key: 'consistency', label: 'Costanza' },
  { key: 'new_artists', label: 'Nuovi Artisti' },
]

const MEDAL_COLORS = ['text-yellow-400', 'text-gray-300', 'text-amber-600']

function RankBadge({ position }) {
  if (position <= 3) {
    return (
      <span className={`w-6 text-center ${MEDAL_COLORS[position - 1]}`}>
        <Trophy size={16} className="inline" />
      </span>
    )
  }
  return (
    <span className="w-6 text-center text-text-muted text-sm font-display">
      {position}
    </span>
  )
}

export default function Leaderboard({ rankings, currentUserId }) {
  const [activeTab, setActiveTab] = useState('obscurity')

  // Hide if all categories empty
  const hasAnyData = CATEGORIES.some(
    (cat) => rankings?.[cat.key]?.length > 0
  )
  if (!hasAnyData) return null

  const currentList = rankings?.[activeTab] || []

  return (
    <div className="bg-surface rounded-xl p-5">
      <h3 className="text-lg font-display text-text-primary mb-4">Classifica</h3>

      {/* Tab bar */}
      <div className="flex gap-1 bg-surface-hover rounded-lg p-1 mb-4 overflow-x-auto">
        {CATEGORIES.map((cat) => (
          <button
            key={cat.key}
            onClick={() => setActiveTab(cat.key)}
            className={`flex-1 min-w-0 px-3 py-1.5 rounded-md text-xs font-medium transition-all whitespace-nowrap
              ${activeTab === cat.key
                ? 'bg-accent text-white'
                : 'text-text-secondary hover:text-text-primary'
              }`}
          >
            {cat.label}
          </button>
        ))}
      </div>

      {/* Ranked list */}
      <AnimatePresence mode="wait">
        <motion.div
          key={activeTab}
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0, y: -8 }}
          transition={{ duration: 0.2 }}
        >
          {currentList.length > 0 ? (
            <StaggerContainer className="space-y-1">
              {currentList.map((entry) => {
                const isCurrentUser = entry.user_id === currentUserId
                return (
                  <StaggerItem key={entry.user_id}>
                    <div
                      className={`flex items-center gap-3 px-3 py-2.5 rounded-lg transition-colors
                        ${isCurrentUser
                          ? 'bg-accent/10 border border-accent/30'
                          : 'hover:bg-surface-hover'
                        }`}
                    >
                      <RankBadge position={entry.rank} />
                      {/* Avatar */}
                      {entry.avatar_url ? (
                        <img
                          src={entry.avatar_url}
                          alt=""
                          className="w-8 h-8 rounded-full object-cover flex-shrink-0"
                        />
                      ) : (
                        <div className="w-8 h-8 rounded-full bg-surface-hover flex items-center justify-center flex-shrink-0">
                          <span className="text-xs text-text-muted">
                            {entry.display_name?.[0]?.toUpperCase() || '?'}
                          </span>
                        </div>
                      )}
                      {/* Name */}
                      <span className="flex-1 text-sm text-text-primary truncate font-body">
                        {entry.display_name}
                      </span>
                      {/* Value */}
                      <span className="text-sm font-display text-text-secondary">
                        {entry.value}
                      </span>
                    </div>
                  </StaggerItem>
                )
              })}
            </StaggerContainer>
          ) : null}
        </motion.div>
      </AnimatePresence>
    </div>
  )
}
