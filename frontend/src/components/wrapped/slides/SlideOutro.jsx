import { useRef } from 'react'
import { motion } from 'framer-motion'
import { Download, Share2 } from 'lucide-react'

export default function SlideOutro({ data }) {
  const cardRef = useRef(null)

  const totalPlays = data?.temporal?.total_plays || 0
  const uniqueArtists = data?.profile?.unique_artists || 0
  const maxStreak = data?.temporal?.streak?.max_streak || 0

  const genres = data?.profile?.genres
  const topGenre = genres
    ? Object.entries(genres).sort((a, b) => b[1] - a[1])[0]?.[0] || null
    : null

  const stats = [
    { label: 'Ascolti totali', value: totalPlays },
    { label: 'Artisti unici', value: uniqueArtists },
    ...(topGenre ? [{ label: 'Genere preferito', value: topGenre }] : []),
    ...(maxStreak ? [{ label: 'Streak massimo', value: `${maxStreak} gg` }] : []),
  ]

  const handleDownload = async () => {
    if (!cardRef.current) return
    try {
      const html2canvas = (await import('html2canvas')).default
      const canvas = await html2canvas(cardRef.current, {
        backgroundColor: '#121212',
        scale: 2,
        useCORS: true,
      })
      const url = canvas.toDataURL('image/png')
      const a = document.createElement('a')
      a.href = url
      a.download = `my-wrapped-${new Date().getFullYear()}.png`
      a.click()
      canvas.remove()
    } catch (err) {
      console.warn('Download failed:', err)
    }
  }

  const handleShare = async () => {
    if (!cardRef.current) return
    let canvas = null
    try {
      const html2canvas = (await import('html2canvas')).default
      canvas = await html2canvas(cardRef.current, {
        backgroundColor: '#121212',
        scale: 2,
        useCORS: true,
      })
      const blob = await new Promise((r) => canvas.toBlob(r, 'image/png'))
      const year = new Date().getFullYear()
      const file = new File([blob], `my-wrapped-${year}.png`, { type: 'image/png' })
      if (navigator.canShare?.({ files: [file] })) {
        await navigator.share({ files: [file], title: `Il Mio Wrapped ${year}` })
        return
      }
    } catch {
      // Fallback to download
    } finally {
      if (canvas) canvas.remove()
    }
    handleDownload()
  }

  return (
    <div className="flex flex-col items-center justify-center min-h-[100dvh] px-6 py-16 relative">
      <motion.h2
        className="text-3xl font-display font-bold text-text-primary mb-8"
        initial={{ opacity: 0, y: -20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.4 }}
      >
        Il Tuo {new Date().getFullYear()} in Musica
      </motion.h2>

      {/* Summary card (captured for export) */}
      <motion.div
        ref={cardRef}
        className="bg-surface rounded-2xl p-8 max-w-md mx-auto w-full"
        initial={{ opacity: 0, scale: 0.95 }}
        animate={{ opacity: 1, scale: 1 }}
        transition={{ duration: 0.5, delay: 0.2 }}
      >
        <div className="space-y-5">
          {stats.map((stat) => (
            <div key={stat.label} className="flex justify-between items-center">
              <span className="text-text-secondary text-sm">{stat.label}</span>
              <span className="text-text-primary font-display font-bold text-lg">
                {stat.value}
              </span>
            </div>
          ))}
        </div>
      </motion.div>

      {/* Action buttons */}
      <motion.div
        className="flex gap-4 mt-8 pointer-events-auto"
        initial={{ opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.6 }}
      >
        <button
          onClick={handleDownload}
          className="flex items-center gap-2 px-5 py-2.5 bg-accent hover:bg-accent-hover text-white rounded-lg font-medium text-sm transition-colors"
        >
          <Download size={16} />
          Scarica
        </button>
        <button
          onClick={handleShare}
          className="flex items-center gap-2 px-5 py-2.5 bg-surface hover:bg-surface-hover text-text-primary border border-border rounded-lg font-medium text-sm transition-colors"
        >
          <Share2 size={16} />
          Condividi
        </button>
      </motion.div>
    </div>
  )
}
