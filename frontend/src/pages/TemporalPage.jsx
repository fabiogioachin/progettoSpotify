import { useState } from 'react'
import { useSpotifyData } from '../hooks/useSpotifyData'
import KPICard from '../components/cards/KPICard'
import ListeningHeatmap from '../components/charts/ListeningHeatmap'
import StreakDisplay from '../components/charts/StreakDisplay'
import SessionStats from '../components/charts/SessionStats'
import { SkeletonKPICard, SkeletonCard } from '../components/ui/Skeleton'
import { StaggerContainer, StaggerItem } from '../components/ui/StaggerContainer'
import { Headphones, Calendar, RefreshCw, TrendingUp } from 'lucide-react'
import SectionErrorBoundary from '../components/ui/SectionErrorBoundary'

const TEMPORAL_RANGES = [
  { value: '7d', label: '7gg' },
  { value: '30d', label: '30gg' },
  { value: '90d', label: '3M' },
  { value: 'all', label: 'Tutto' },
]

export default function TemporalPage() {
  const [range, setRange] = useState('30d')
  const { data, loading, error, refetch } = useSpotifyData('/api/v1/temporal', { range })

  const heatmap = data?.heatmap || {}
  const sessions = data?.sessions || {}
  const peakHours = data?.peak_hours || []
  const patterns = data?.patterns || {}
  const streak = data?.streak || {}
  const totalPlays = data?.total_plays || 0
  const mostPlayed = data?.most_played || {}
  const topTracks = data?.top_tracks || []
  const accumulated = data?.accumulated || false
  const newPlaysStored = data?.new_plays_stored || 0

  const peakHourLabel = peakHours.length > 0 ? `${String(peakHours[0].hour).padStart(2, '0')}:00` : '--'

  return (
    <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-6">
        <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3">
          <div>
            <h1 className="text-2xl font-display font-bold text-text-primary">Pattern Temporali</h1>
            <p className="text-text-secondary text-sm mt-1">Quando e come ascolti la tua musica</p>
          </div>
          <div className="flex items-center gap-2">
            <div className="flex gap-1">
              {TEMPORAL_RANGES.map((r) => (
                <button
                  key={r.value}
                  onClick={() => setRange(r.value)}
                  className={`px-3 py-1.5 min-h-[36px] text-xs rounded transition-colors ${
                    range === r.value
                      ? 'bg-accent text-white'
                      : 'bg-surface-hover text-text-muted hover:text-text-primary'
                  }`}
                >
                  {r.label}
                </button>
              ))}
            </div>
            <button onClick={() => refetch()} className="p-2 min-h-[36px] min-w-[36px] rounded-lg text-text-muted hover:text-text-primary hover:bg-surface-hover transition-all duration-300" title="Aggiorna">
              <RefreshCw size={18} />
            </button>
          </div>
        </div>

        {/* Data source info */}
        <div className="bg-accent/5 border border-accent/10 rounded-xl px-4 py-2 text-text-secondary text-xs flex flex-wrap items-center gap-2">
          {accumulated ? (
            <>
              <TrendingUp size={14} className="text-accent flex-shrink-0" />
              <span>Basato su {totalPlays} ascolti accumulati</span>
              {newPlaysStored > 0 && (
                <span className="text-accent font-medium">
                  (+{newPlaysStored} nuovi salvati)
                </span>
              )}
              <span className="text-text-muted sm:ml-auto">Lo storico cresce ad ogni visita</span>
            </>
          ) : (
            <>
              <span>Basato sugli ultimi {totalPlays} ascolti (limite API Spotify: 50).</span>
              <span className="text-text-muted sm:ml-auto">I dati si accumulano ad ogni visita</span>
            </>
          )}
        </div>

        {error && (
          <div className="bg-red-500/10 border border-red-500/20 rounded-xl p-4 text-red-400 text-sm">{error}</div>
        )}

        {loading ? (
          <div className="space-y-6">
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <SkeletonKPICard />
              <SkeletonKPICard />
            </div>
            <SkeletonCard height="h-64" />
          </div>
        ) : (
          <>
            {/* KPI Cards */}
            <SectionErrorBoundary sectionName="KPICards">
              <StaggerContainer className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <StaggerItem>
                  <KPICard title="Ascolti Totali" value={totalPlays} icon={Headphones} delay={0} tooltip="Numero totale di ascolti registrati nel database. Cresce ad ogni visita della pagina" />
                </StaggerItem>
                <StaggerItem>
                  <KPICard title="Ora di Punta" value={peakHourLabel} icon={Calendar} delay={100} tooltip="L'ora del giorno in cui ascolti più musica, basata sullo storico accumulato" />
                </StaggerItem>
              </StaggerContainer>
            </SectionErrorBoundary>

            {/* Heatmap */}
            <SectionErrorBoundary sectionName="ListeningHeatmap">
              <ListeningHeatmap
                data={heatmap.data || []}
                dayLabels={heatmap.day_labels || []}
                hourLabels={heatmap.hour_labels || []}
              />
            </SectionErrorBoundary>

            {/* Streak + Sessions */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <SectionErrorBoundary sectionName="StreakDisplay">
                <StreakDisplay
                  streak={streak.max_streak || 0}
                  uniqueDays={streak.unique_days || 0}
                  activeDays={streak.active_last_7 || []}
                />
              </SectionErrorBoundary>
              <SectionErrorBoundary sectionName="SessionStats">
                <SessionStats
                  sessions={sessions}
                  patterns={patterns}
                  mostPlayed={mostPlayed}
                />
              </SectionErrorBoundary>
            </div>

            {/* Top tracks from history */}
            {topTracks.length > 0 && (
              <SectionErrorBoundary sectionName="TopTracks">
                <div className="glow-card bg-surface rounded-xl p-5">
                  <h3 className="text-text-primary font-display font-semibold mb-4">Brani Più Ascoltati</h3>
                  <StaggerContainer className="space-y-2">
                    {topTracks.map((t, i) => (
                      <StaggerItem key={i}>
                        <div className="flex items-center gap-3 p-2 rounded-lg hover:bg-surface-hover transition-all duration-300">
                          <span className="w-6 text-center text-text-muted text-sm font-mono">{i + 1}</span>
                          <div className="flex-1 min-w-0">
                            <p className="text-text-primary text-sm truncate">{t.name}</p>
                          </div>
                          <span className="text-accent text-sm font-medium">{t.count}×</span>
                        </div>
                      </StaggerItem>
                    ))}
                  </StaggerContainer>
                </div>
              </SectionErrorBoundary>
            )}

            {/* Peak Hours */}
            {peakHours.length > 0 && (
              <SectionErrorBoundary sectionName="PeakHours">
                <div className="glow-card bg-surface rounded-xl p-5">
                  <h3 className="text-text-primary font-display font-semibold mb-4">Ore di Punta</h3>
                  <StaggerContainer className="flex gap-4 flex-wrap">
                    {peakHours.map((ph, i) => (
                      <StaggerItem key={i}>
                        <div className="flex items-center gap-3 bg-surface-hover rounded-lg px-4 py-3">
                          <span className="text-2xl font-display font-bold text-accent">{String(ph.hour).padStart(2, '0')}:00</span>
                          <span className="text-text-secondary text-sm">{ph.count} ascolti</span>
                        </div>
                      </StaggerItem>
                    ))}
                  </StaggerContainer>
                </div>
              </SectionErrorBoundary>
            )}
          </>
        )}
      </main>
  )
}
