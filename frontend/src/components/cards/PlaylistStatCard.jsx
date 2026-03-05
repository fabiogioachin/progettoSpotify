import { useState } from 'react'
import { Music, Users, Calendar, Clock, ChevronDown, ChevronUp } from 'lucide-react'
import api from '../../lib/api'

export default function PlaylistStatCard({ playlist, index = 0 }) {
  const [expanded, setExpanded] = useState(false)
  const [tracks, setTracks] = useState(null)
  const [loadingTracks, setLoadingTracks] = useState(false)

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

  async function handleToggle() {
    if (!expanded && !tracks) {
      setLoadingTracks(true)
      try {
        const { data } = await api.get(`/api/playlists/${playlist.id}/tracks`, {
          params: { limit: 100, offset: 0 },
        })
        setTracks(data.tracks || [])
      } catch {
        setTracks([])
      } finally {
        setLoadingTracks(false)
      }
    }
    setExpanded(!expanded)
  }

  return (
    <div
      className="glow-card bg-surface rounded-xl p-4 animate-slide-up cursor-pointer transition-all duration-300 hover:ring-1 hover:ring-accent/20"
      style={{ animationDelay: `${index * 50}ms` }}
      onClick={handleToggle}
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
        <div className="text-text-muted">
          {expanded ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
        </div>
      </div>

      <div className="space-y-2">
        <MiniStat icon={Music} label="Tracce" value={playlist.track_count} />
        <MiniStat icon={Users} label="Artisti unici" value={playlist.unique_artists} />
        <div>
          <div className="flex items-center justify-between mb-1">
            <span className="text-text-muted text-xs">Diversit&agrave; artisti</span>
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

      {/* Expanded track list */}
      {expanded && (
        <div className="mt-3 pt-3 border-t border-border" onClick={(e) => e.stopPropagation()}>
          {loadingTracks ? (
            <div className="flex justify-center py-4">
              <div className="w-5 h-5 border-2 border-accent border-t-transparent rounded-full animate-spin" />
            </div>
          ) : tracks && tracks.length > 0 ? (
            <div className="space-y-1 max-h-60 overflow-y-auto pr-1">
              {tracks.map((t, i) => (
                <div key={t.id} className="flex items-center gap-2 p-1.5 rounded hover:bg-surface-hover transition-colors">
                  <span className="w-5 text-center text-text-muted text-[10px] font-mono flex-shrink-0">{i + 1}</span>
                  {t.album_image ? (
                    <img src={t.album_image} alt={t.name} className="w-8 h-8 rounded object-cover flex-shrink-0" />
                  ) : (
                    <div className="w-8 h-8 rounded bg-surface-hover flex items-center justify-center flex-shrink-0">
                      <Music size={12} className="text-text-muted" />
                    </div>
                  )}
                  <div className="min-w-0 flex-1">
                    <p className="text-text-primary text-xs truncate">{t.name}</p>
                    <p className="text-text-muted text-[10px] truncate">{t.artist}</p>
                  </div>
                  <span className="text-text-muted text-[10px] flex-shrink-0">Pop. {t.popularity}</span>
                </div>
              ))}
            </div>
          ) : (
            <p className="text-text-muted text-xs text-center py-2">Nessun brano trovato</p>
          )}
        </div>
      )}
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
