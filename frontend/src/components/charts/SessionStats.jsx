import { useState, useEffect } from 'react'
import { Headphones, Music, Clock, Zap } from 'lucide-react'

export default function SessionStats({
  sessions = {},
  patterns = {},
  mostPlayed = null,
}) {
  const {
    count = 0,
    avg_duration_minutes = 0,
    longest_session_minutes = 0,
    avg_tracks_per_session = 0,
  } = sessions

  const {
    weekday_plays = 0,
    weekend_plays = 0,
    weekday_pct = 50,
  } = patterns

  // Animated bars: trigger width transition after mount
  const [mounted, setMounted] = useState(false)
  useEffect(() => {
    const timer = setTimeout(() => setMounted(true), 100)
    return () => clearTimeout(timer)
  }, [])

  const avgDurationRounded = Math.round(avg_duration_minutes)
  const avgTracksRounded = Math.round(avg_tracks_per_session)
  const avgDurationPct = Math.min((avg_duration_minutes / 60) * 100, 100)
  const avgTracksPct = Math.min((avg_tracks_per_session / 30) * 100, 100)
  const weekendPct = 100 - weekday_pct

  return (
    <div className="glow-card bg-surface rounded-xl p-6 animate-slide-up">
      {/* Header */}
      <div className="flex items-center gap-2 mb-6">
        <Headphones size={20} className="text-accent" />
        <h3 className="text-text-primary font-display font-semibold text-lg">Le Tue Sessioni</h3>
      </div>

      {/* Stats grid - 2 columns */}
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 mb-6">
        {/* Sessione media */}
        <StatCard
          icon={Clock}
          label="Sessione media"
          value={avgDurationRounded}
          suffix="min"
          barPct={mounted ? avgDurationPct : 0}
          barColor="bg-accent"
        />

        {/* Tracce per sessione */}
        <StatCard
          icon={Music}
          label="Tracce per sessione"
          value={avgTracksRounded}
          suffix=""
          barPct={mounted ? avgTracksPct : 0}
          barColor="bg-accent"
        />

        {/* Sessione record */}
        <div className="bg-surface-hover rounded-xl p-4">
          <div className="flex items-center gap-2 mb-2">
            <Zap size={14} className="text-amber-400" />
            <span className="text-text-muted text-xs uppercase tracking-wide">Sessione record</span>
          </div>
          <div className="flex items-end gap-2">
            <span className="text-text-primary font-display font-bold text-3xl">{Math.round(longest_session_minutes)}</span>
            <span className="text-text-secondary text-sm mb-1">min</span>
          </div>
          <div className="mt-2">
            <span className="inline-block text-[10px] font-medium text-accent bg-accent/10 px-2 py-0.5 rounded-full">
              Record personale
            </span>
          </div>
        </div>

        {/* Totale sessioni */}
        <div className="bg-surface-hover rounded-xl p-4">
          <div className="flex items-center gap-2 mb-2">
            <Headphones size={14} className="text-text-muted" />
            <span className="text-text-muted text-xs uppercase tracking-wide">Totale sessioni</span>
          </div>
          <span className="text-text-primary font-display font-bold text-3xl">{count}</span>
        </div>
      </div>

      {/* Weekend vs Weekday section */}
      <div className="mb-6">
        <p className="text-text-muted text-xs uppercase tracking-wide mb-3">Feriali vs Weekend</p>
        <div className="space-y-3">
          {/* Weekday bar */}
          <div>
            <div className="flex items-center justify-between mb-1">
              <span className="text-text-secondary text-sm">Feriali</span>
              <span className="text-text-muted text-xs">{weekday_plays.toLocaleString('it-IT')} ascolti</span>
            </div>
            <div className="h-3 bg-background rounded-full overflow-hidden">
              <div
                className="h-full bg-accent rounded-full transition-all duration-1000 ease-out"
                style={{ width: mounted ? `${weekday_pct}%` : '0%' }}
              />
            </div>
          </div>

          {/* Weekend bar */}
          <div>
            <div className="flex items-center justify-between mb-1">
              <span className="text-text-secondary text-sm">Weekend</span>
              <span className="text-text-muted text-xs">{weekend_plays.toLocaleString('it-IT')} ascolti</span>
            </div>
            <div className="h-3 bg-background rounded-full overflow-hidden">
              <div
                className="h-full bg-spotify rounded-full transition-all duration-1000 ease-out"
                style={{ width: mounted ? `${weekendPct}%` : '0%' }}
              />
            </div>
          </div>
        </div>
      </div>

      {/* Most played track */}
      {mostPlayed && mostPlayed.track_name && (
        <div className="bg-surface-hover rounded-xl p-4 flex items-center gap-3">
          <div className="w-10 h-10 rounded-lg bg-accent/10 flex items-center justify-center flex-shrink-0">
            <Music size={18} className="text-accent" />
          </div>
          <div className="min-w-0">
            <p className="text-text-muted text-[10px] uppercase tracking-wide mb-0.5">Brano piu ascoltato</p>
            <p className="text-text-primary text-sm font-semibold truncate">{mostPlayed.track_name}</p>
          </div>
          <span className="ml-auto text-accent font-display font-bold text-lg flex-shrink-0">
            {mostPlayed.count}x
          </span>
        </div>
      )}
    </div>
  )
}

/**
 * Reusable stat card with animated progress bar.
 */
function StatCard({ icon: Icon, label, value, suffix, barPct, barColor }) {
  return (
    <div className="bg-surface-hover rounded-xl p-4">
      <div className="flex items-center gap-2 mb-2">
        <Icon size={14} className="text-text-muted" />
        <span className="text-text-muted text-xs uppercase tracking-wide">{label}</span>
      </div>
      <div className="flex items-end gap-2 mb-3">
        <span className="text-text-primary font-display font-bold text-3xl">{value}</span>
        {suffix && <span className="text-text-secondary text-sm mb-1">{suffix}</span>}
      </div>
      <div className="h-2 bg-background rounded-full overflow-hidden">
        <div
          className={`h-full ${barColor} rounded-full transition-all duration-1000 ease-out`}
          style={{ width: `${barPct}%` }}
        />
      </div>
    </div>
  )
}
