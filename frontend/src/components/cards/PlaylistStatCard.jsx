import { motion } from 'framer-motion'
import { Music, Users, Calendar, Clock } from 'lucide-react'

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

  const concentrationPct = Math.round(playlist.artist_concentration * 100)

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
        <div>
          <div className="flex items-center justify-between mb-1">
            <span className="text-text-muted text-xs">Diversità artisti</span>
            <span className="text-text-primary text-xs font-medium">{concentrationPct}%</span>
          </div>
          <div className="w-full h-1.5 bg-background rounded-full overflow-hidden">
            <div
              className="h-full rounded-full transition-all duration-500"
              style={{
                width: `${concentrationPct}%`,
                backgroundColor: concentrationPct > 70 ? '#1DB954' : concentrationPct > 40 ? '#f59e0b' : '#ef4444',
              }}
            />
          </div>
        </div>
        <MiniStat icon={Calendar} label="Anno medio" value={freshnessLabel} />
        <MiniStat icon={Clock} label="Ultimo aggiornamento" value={stalenessLabel} />
      </div>
    </motion.div>
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
