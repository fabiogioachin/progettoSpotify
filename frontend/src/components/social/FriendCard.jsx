import { UserCircle, X, ArrowRightLeft } from 'lucide-react'
import { motion } from 'framer-motion'

function formatSinceDate(dateString) {
  if (!dateString) return ''
  const date = new Date(dateString)
  const now = new Date()
  const diffMs = now - date
  const diffDays = Math.floor(diffMs / (1000 * 60 * 60 * 24))

  if (diffDays < 1) return 'da oggi'
  if (diffDays === 1) return 'da ieri'
  if (diffDays < 30) return `da ${diffDays} giorni`
  const diffMonths = Math.floor(diffDays / 30)
  if (diffMonths === 1) return 'da 1 mese'
  if (diffMonths < 12) return `da ${diffMonths} mesi`
  const diffYears = Math.floor(diffDays / 365)
  if (diffYears === 1) return 'da 1 anno'
  return `da ${diffYears} anni`
}

export default function FriendCard({ friend, onCompare, onRemove }) {
  const handleRemove = () => {
    if (window.confirm(`Rimuovere ${friend.display_name} dagli amici?`)) {
      onRemove(friend.id)
    }
  }

  return (
    <motion.div
      className="glow-card bg-surface rounded-xl p-4 flex items-center gap-4 relative group"
      whileHover={{ scale: 1.02 }}
      transition={{ duration: 0.2 }}
    >
      {/* Avatar */}
      {friend.avatar_url ? (
        <img
          src={friend.avatar_url}
          alt=""
          className="w-12 h-12 rounded-full object-cover flex-shrink-0"
        />
      ) : (
        <div className="w-12 h-12 rounded-full bg-surface-hover flex items-center justify-center flex-shrink-0">
          <UserCircle size={24} className="text-text-muted" />
        </div>
      )}

      {/* Info */}
      <div className="flex-1 min-w-0">
        <p className="text-sm font-display text-text-primary truncate">
          {friend.display_name}
        </p>
        <p className="text-[11px] text-text-muted">
          Amici {formatSinceDate(friend.since)}
        </p>
      </div>

      {/* Actions */}
      <div className="flex items-center gap-1.5">
        <button
          onClick={() => onCompare(friend)}
          className="px-3 py-1.5 bg-accent hover:bg-accent-hover text-white text-xs font-medium rounded-lg transition-colors flex items-center gap-1.5"
        >
          <ArrowRightLeft size={12} />
          Confronta
        </button>
        <button
          onClick={handleRemove}
          className="p-1.5 text-text-muted hover:text-red-400 transition-colors opacity-0 group-hover:opacity-100 focus:opacity-100"
          aria-label={`Rimuovi ${friend.display_name}`}
        >
          <X size={14} />
        </button>
      </div>
    </motion.div>
  )
}
