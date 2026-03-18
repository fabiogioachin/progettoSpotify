import { useEffect, useRef, useState } from 'react'
import { X, Copy, Check } from 'lucide-react'
import { AnimatePresence, motion } from 'framer-motion'

export default function InviteModal({ isOpen, onClose, inviteCode }) {
  const [copied, setCopied] = useState(false)
  const inputRef = useRef(null)

  const inviteUrl = inviteCode
    ? `${window.location.origin}/invite/${inviteCode}`
    : ''

  // Close on Escape
  useEffect(() => {
    if (!isOpen) return
    function handleKey(e) {
      if (e.key === 'Escape') onClose()
    }
    document.addEventListener('keydown', handleKey)
    return () => document.removeEventListener('keydown', handleKey)
  }, [isOpen, onClose])

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(inviteUrl)
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    } catch {
      // Fallback: select all
      inputRef.current?.select()
    }
  }

  const handleInputClick = () => {
    inputRef.current?.select()
  }

  return (
    <AnimatePresence>
      {isOpen && (
        <motion.div
          className="fixed inset-0 z-50 flex items-center justify-center p-4"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          transition={{ duration: 0.2 }}
        >
          {/* Overlay */}
          <div className="absolute inset-0 bg-black/60" onClick={onClose} />

          {/* Dialog */}
          <motion.div
            role="dialog"
            aria-modal="true"
            aria-label="Invita un amico"
            className="relative bg-surface border border-border rounded-xl p-6 w-full max-w-md shadow-xl"
            initial={{ scale: 0.95, opacity: 0 }}
            animate={{ scale: 1, opacity: 1 }}
            exit={{ scale: 0.95, opacity: 0 }}
            transition={{ duration: 0.2 }}
          >
            {/* Close button */}
            <button
              onClick={onClose}
              className="absolute top-3 right-3 p-1.5 text-text-muted hover:text-text-primary transition-colors"
              aria-label="Chiudi"
            >
              <X size={18} />
            </button>

            <h2 className="text-lg font-display text-text-primary mb-2">
              Invita un amico
            </h2>
            <p className="text-sm text-text-secondary mb-4">
              Condividi questo link per aggiungere un amico.
            </p>

            {/* Link input + copy */}
            <div className="flex gap-2">
              <input
                ref={inputRef}
                type="text"
                readOnly
                value={inviteUrl}
                onClick={handleInputClick}
                className="flex-1 bg-surface-hover border border-border rounded-lg px-3 py-2 text-sm text-text-primary font-mono select-all focus:outline-none focus:ring-2 focus:ring-accent"
              />
              <button
                onClick={handleCopy}
                className="px-3 py-2 bg-accent hover:bg-accent-hover text-white rounded-lg transition-colors flex items-center gap-1.5 text-sm font-medium"
              >
                {copied ? (
                  <>
                    <Check size={14} />
                    Copiato!
                  </>
                ) : (
                  <>
                    <Copy size={14} />
                    Copia
                  </>
                )}
              </button>
            </div>

            <p className="text-[11px] text-text-muted mt-3">
              Valido per 7 giorni
            </p>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  )
}
