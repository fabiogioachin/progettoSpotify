import { motion } from 'framer-motion'
import { Inbox } from 'lucide-react'

export default function EmptyState({
  icon: Icon = Inbox,
  message,
  description,
  action,
  className = '',
}) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3, ease: 'easeOut' }}
      className={`flex flex-col items-center justify-center min-h-[12rem] gap-3 ${className}`}
    >
      <Icon size={48} className="text-text-muted" />

      <p className="text-text-secondary font-medium text-base text-center">
        {message}
      </p>

      {description && (
        <p className="text-text-muted text-sm text-center max-w-sm">
          {description}
        </p>
      )}

      {action && (
        <button
          onClick={action.onClick}
          className="mt-2 bg-accent hover:bg-accent-hover text-white px-4 py-2 rounded-lg transition-colors"
        >
          {action.label}
        </button>
      )}
    </motion.div>
  )
}
