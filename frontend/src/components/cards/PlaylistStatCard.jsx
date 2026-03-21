import { useState } from 'react'
import { motion } from 'framer-motion'
import { Music, Users, Calendar, Clock, Info } from 'lucide-react'

export default function PlaylistStatCard({ playlist, index = 0 }) {
  if (!playlist) return null

  const freshnessLabel = playlist.freshness_year > 0
    ? `${Math.round(playlist.freshness_year)}`
    : '—'

  const stalenessLabel = playlist.staleness_days >= 0
    ? playlist.staleness_days === 0 ? 'Oggi'
      : playlist.staleness_days < 30 ? `${playlist.staleness_days}gg fa`
      : playlist.staleness_days < 365 ? `${Math.round(playlist.staleness_days / 30)}m fa`
      : `${Math.round(playlist.staleness_days / 365)}a fa`
    : '—'

  const concentrationPct = Math.min(Math.round(playlist.artist_concentration * 100), 100)

  return (
    <motion.div
      className="glow-card bg-surface rounded-xl p-4"
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3, delay: index * 0.05 }}
    >
      <div className="flex items-start gap-3 mb-3">
        {playlist.image ? (
          <img src={playlist.image} alt={playlist.name} className="w-14 h-14 rounded-lg object-cover flex-shrink-0" />
        ) : (
          <div className="w-14 h-14 rounded-lg bg-surface-hover flex items-center justify-center flex-shrink-0">
            <Music size={20} className="text-text-muted" />
          </div>
        )}
        <div className="min-w-0 flex-1">
          <p className="text-text-primary text-sm font-medium truncate">{playlist.name}</p>
          <div className="flex items-center gap-2 mt-1">
            {playlist.is_public && (
              <span className="text-[10px] px-1.5 py-0.5 rounded bg-accent/10 text-accent">Pubblica</span>
            )}
            {playlist.is_collaborative && (
              <span className="text-[10px] px-1.5 py-0.5 rounded bg-emerald-500/10 text-emerald-400">Collaborativa</span>
            )}
          </div>
        </div>
      </div>

      <div className="space-y-2">
        <MiniStat icon={Music} label="Tracce" value={playlist.track_count} />
        <MiniStat icon={Users} label="Artisti unici" value={playlist.unique_artists} />
        <VarietaArtisti
          concentrationPct={concentrationPct}
          uniqueArtists={playlist.unique_artists}
          trackCount={playlist.track_count}
        />
        <MiniStat icon={Calendar} label="Anno medio" value={freshnessLabel} />
        <MiniStat icon={Clock} label="Ultimo aggiornamento" value={stalenessLabel} />
      </div>
    </motion.div>
  )
}

function VarietaArtisti({ concentrationPct, uniqueArtists, trackCount }) {
  const [showTooltip, setShowTooltip] = useState(false)

  return (
    <div className="relative">
      <div className="flex items-center justify-between mb-1">
        <div className="flex items-center gap-1">
          <span className="text-text-muted text-xs">Varietà artisti</span>
          <button
            type="button"
            className="text-text-muted hover:text-text-secondary transition-colors"
            onMouseEnter={() => setShowTooltip(true)}
            onMouseLeave={() => setShowTooltip(false)}
            onFocus={() => setShowTooltip(true)}
            onBlur={() => setShowTooltip(false)}
            aria-label="Info varietà artisti"
          >
            <Info size={10} />
          </button>
        </div>
        <span className="text-text-primary text-xs font-medium">
          {concentrationPct}% ({uniqueArtists} artisti / {trackCount} brani)
        </span>
      </div>
      {showTooltip && (
        <div className="absolute z-10 bottom-full left-0 mb-1 px-2.5 py-1.5 rounded-lg bg-background border border-surface-hover text-text-secondary text-[10px] leading-relaxed w-56 shadow-lg">
          Rapporto tra artisti unici e brani totali. 100% = ogni brano ha un artista diverso, 50% = metà dei brani condivide artisti.
        </div>
      )}
      <div className="w-full h-1.5 bg-background rounded-full overflow-hidden">
        <div
          className="h-full rounded-full transition-all duration-500"
          style={{
            width: `${concentrationPct}%`,
            backgroundColor: concentrationPct > 70 ? '#6366f1' : concentrationPct > 40 ? '#f59e0b' : '#ef4444',
          }}
        />
      </div>
    </div>
  )
}

function MiniStat({ icon: Icon, label, value }) {
  return (
    <div className="flex items-center justify-between">
      <div className="flex items-center gap-1.5">
        <Icon size={12} className="text-text-muted" />
        <span className="text-text-muted text-xs">{label}</span>
      </div>
      <span className="text-text-primary text-xs font-medium">{value}</span>
    </div>
  )
}
