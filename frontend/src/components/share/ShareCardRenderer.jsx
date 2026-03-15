import { useRef, useCallback, useEffect } from 'react'
import { motion } from 'framer-motion'
import { Download, Share2, X } from 'lucide-react'
import html2canvas from 'html2canvas'

export default function ShareCardRenderer({ children, filename = 'my-music-card', onClose }) {
  const cardRef = useRef(null)

  useEffect(() => {
    const handleKeyDown = (e) => {
      if (e.key === 'Escape') onClose?.()
    }
    document.addEventListener('keydown', handleKeyDown)
    return () => document.removeEventListener('keydown', handleKeyDown)
  }, [onClose])

  const handleDownload = useCallback(async () => {
    if (!cardRef.current) return
    try {
      const canvas = await html2canvas(cardRef.current, {
        backgroundColor: '#121212',
        scale: 2,
        useCORS: true,
      })
      const url = canvas.toDataURL('image/png')
      const a = document.createElement('a')
      a.href = url
      a.download = `${filename}.png`
      a.click()
      canvas.remove()
    } catch (err) {
      console.warn('Download failed:', err)
    }
  }, [filename])

  const handleShare = useCallback(async () => {
    if (!cardRef.current) return
    let canvas
    try {
      canvas = await html2canvas(cardRef.current, { backgroundColor: '#121212', scale: 2, useCORS: true })
      const blob = await new Promise(resolve => canvas.toBlob(resolve, 'image/png'))
      if (!blob) {
        handleDownload()
        return
      }
      const file = new File([blob], `${filename}.png`, { type: 'image/png' })
      if (navigator.canShare?.({ files: [file] })) {
        await navigator.share({ files: [file], title: 'La mia musica' })
      } else {
        handleDownload()
      }
    } catch {
      handleDownload()
    } finally {
      canvas?.remove()
    }
  }, [filename, handleDownload])

  return (
      <motion.div
        role="dialog"
        aria-modal="true"
        aria-label="Condividi card"
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        exit={{ opacity: 0 }}
        transition={{ duration: 0.2 }}
        className="fixed inset-0 z-[60] bg-black/70 flex items-center justify-center p-4"
        onClick={(e) => { if (e.target === e.currentTarget) onClose?.() }}
      >
        <motion.div
          initial={{ scale: 0.9, opacity: 0 }}
          animate={{ scale: 1, opacity: 1 }}
          exit={{ scale: 0.9, opacity: 0 }}
          transition={{ duration: 0.25, ease: 'easeOut' }}
          className="relative flex flex-col items-center gap-4 max-h-[90vh] overflow-y-auto"
        >
          {/* Close button */}
          <button
            onClick={onClose}
            className="absolute -top-2 -right-2 z-10 w-8 h-8 rounded-full bg-surface-hover flex items-center justify-center text-text-secondary hover:text-text-primary transition-colors"
            aria-label="Chiudi"
          >
            <X size={16} />
          </button>

          {/* Card to capture */}
          <div ref={cardRef}>
            {children}
          </div>

          {/* Action buttons */}
          <div className="flex gap-3">
            <button
              onClick={handleDownload}
              className="flex items-center gap-2 px-4 py-2.5 bg-surface hover:bg-surface-hover text-text-primary rounded-lg text-sm font-medium transition-colors"
            >
              <Download size={16} aria-hidden="true" />
              Scarica
            </button>
            <button
              onClick={handleShare}
              className="flex items-center gap-2 px-4 py-2.5 bg-accent hover:bg-accent-hover text-white rounded-lg text-sm font-medium transition-colors"
            >
              <Share2 size={16} aria-hidden="true" />
              Condividi
            </button>
          </div>
        </motion.div>
      </motion.div>
  )
}
