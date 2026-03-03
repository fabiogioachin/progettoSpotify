import { useSpotifyData } from '../hooks/useSpotifyData'
import KPICard from '../components/cards/KPICard'
import ListeningHeatmap from '../components/charts/ListeningHeatmap'
import StreakDisplay from '../components/charts/StreakDisplay'
import SessionStats from '../components/charts/SessionStats'
import LoadingSpinner from '../components/ui/LoadingSpinner'
import { Headphones, Calendar, RefreshCw } from 'lucide-react'

export default function TemporalPage() {
  const { data, loading, error, refetch } = useSpotifyData('/api/temporal')

  const heatmap = data?.heatmap || {}
  const sessions = data?.sessions || {}
  const peakHours = data?.peak_hours || []
  const patterns = data?.patterns || {}
  const streak = data?.streak || {}
  const totalPlays = data?.total_plays || 0
  const mostPlayed = data?.most_played || {}

  const peakHourLabel = peakHours.length > 0 ? `${String(peakHours[0].hour).padStart(2, '0')}:00` : '--'

  return (
    <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-6">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-display font-bold text-text-primary">Pattern Temporali</h1>
            <p className="text-text-secondary text-sm mt-1">Quando e come ascolti la tua musica</p>
          </div>
          <button onClick={() => refetch()} className="p-2 rounded-lg text-text-muted hover:text-text-primary hover:bg-surface-hover transition-all duration-300" title="Aggiorna">
            <RefreshCw size={18} />
          </button>
        </div>

        {/* Spotify API limit notice */}
        <div className="bg-accent/5 border border-accent/10 rounded-xl px-4 py-2 text-text-secondary text-xs">
          Basato sugli ultimi {totalPlays} ascolti (limite API Spotify: 50)
        </div>

        {error && (
          <div className="bg-red-500/10 border border-red-500/20 rounded-xl p-4 text-red-400 text-sm">{error}</div>
        )}

        {loading ? (
          <LoadingSpinner />
        ) : (
          <>
            {/* KPI Cards — simplified to 2 (streak and sessions moved to dedicated components) */}
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <KPICard title="Ascolti Totali" value={totalPlays} icon={Headphones} delay={0} />
              <KPICard title="Ora di Punta" value={peakHourLabel} icon={Calendar} delay={100} />
            </div>

            {/* Heatmap — Spotify Wrapped style */}
            <ListeningHeatmap
              data={heatmap.data || []}
              dayLabels={heatmap.day_labels || []}
              hourLabels={heatmap.hour_labels || []}
            />

            {/* Streak + Sessions — Duolingo style, side by side */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <StreakDisplay
                streak={streak.max_streak || 0}
                uniqueDays={streak.unique_days || 0}
              />
              <SessionStats
                sessions={sessions}
                patterns={patterns}
                mostPlayed={mostPlayed}
              />
            </div>

            {/* Peak Hours */}
            {peakHours.length > 0 && (
              <div className="glow-card bg-surface rounded-xl p-5">
                <h3 className="text-text-primary font-display font-semibold mb-4">Ore di Punta</h3>
                <div className="flex gap-4 flex-wrap">
                  {peakHours.map((ph, i) => (
                    <div key={i} className="flex items-center gap-3 bg-surface-hover rounded-lg px-4 py-3">
                      <span className="text-2xl font-display font-bold text-accent">{String(ph.hour).padStart(2, '0')}:00</span>
                      <span className="text-text-secondary text-sm">{ph.count} ascolti</span>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </>
        )}
      </main>
  )
}
