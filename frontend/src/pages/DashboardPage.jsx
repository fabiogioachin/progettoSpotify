import { useState } from 'react'
import { Disc3, Flame, Music, Users } from 'lucide-react'
import KPICard from '../components/cards/KPICard'
import TrackCard from '../components/cards/TrackCard'
import AudioRadar from '../components/charts/AudioRadar'
import TrendTimeline from '../components/charts/TrendTimeline'
import GenreTreemap from '../components/charts/GenreTreemap'
import ClaudeExportPanel from '../components/export/ClaudeExportPanel'
import PeriodSelector from '../components/ui/PeriodSelector'
import { SkeletonKPICard, SkeletonCard } from '../components/ui/Skeleton'
import { StaggerContainer, StaggerItem } from '../components/ui/StaggerContainer'
import { useSpotifyData } from '../hooks/useSpotifyData'

export default function DashboardPage() {
    const [period, setPeriod] = useState('medium_term')

  const { data: topData, loading: topLoading, error: topError } = useSpotifyData(
        '/api/library/top',
    { time_range: period, limit: 50 }
      )

  const { data: trendsData, loading: trendsLoading, error: trendsError } = useSpotifyData('/api/analytics/trends')
  const { data: temporalData } = useSpotifyData('/api/temporal')
  const { data: featuresData, loading: featuresLoading, error: featuresError } = useSpotifyData(
    '/api/analytics/features',
    { time_range: period }
  )

  const tracks = topData?.tracks || []
      const features = featuresData?.features || {}
          const genres = featuresData?.genres || {}
              const trends = trendsData?.current || []

                  // KPI calculations — solo dati reali sempre disponibili
                  const trackCount = topData?.total || tracks.length || 0

  // Streak di ascolto
  const streak = temporalData?.streak?.max_streak || 0

  // Artisti unici: preferisci backend, fallback dal conteggio tracks
  let uniqueArtists = featuresData?.unique_artists || 0
    if (uniqueArtists === 0 && tracks.length > 0) {
          const artistNames = new Set()
          tracks.forEach(t => {
                  if (t.artist) artistNames.add(t.artist)
                  if (t.artists) t.artists.forEach(a => { if (a.name) artistNames.add(a.name) })
          })
          uniqueArtists = artistNames.size
    }

  const topGenre = Object.keys(genres)[0] || null
    const topGenrePct = Object.values(genres)[0] || 0

  const isLoading = topLoading || trendsLoading || featuresLoading
    const hasError = topError || trendsError || featuresError

  return (
    <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-6">
        {/* Header row */}
        <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
          <div>
            <h1 className="text-2xl font-display font-bold text-text-primary">Dashboard</h1>
            <p className="text-text-secondary text-sm">Panoramica del tuo profilo musicale</p>
          </div>
          <PeriodSelector value={period} onChange={setPeriod} />
        </div>

        {isLoading ? (
          <div className="space-y-6">
            <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-4">
              {Array.from({ length: 4 }).map((_, i) => (
                <SkeletonKPICard key={i} />
              ))}
            </div>
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
              <SkeletonCard height="h-72" />
              <SkeletonCard height="h-72" />
            </div>
          </div>
        ) : (
          <>
            {hasError && (
              <div className="text-red-400 text-sm bg-red-400/10 p-3 rounded-lg">
                Errore nel caricamento dei dati. Riprova tra qualche istante.
              </div>
            )}

            {/* KPI Row — dati reali sempre disponibili */}
            <StaggerContainer className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-4">
              <StaggerItem>
                <KPICard
                  title="Brani analizzati"
                  value={trackCount}
                  icon={Music}
                  delay={0}
                  tooltip="Numero di brani nel tuo periodo di ascolto selezionato"
                />
              </StaggerItem>
              <StaggerItem>
                <KPICard
                  title="Streak di ascolto"
                  value={streak}
                  suffix=" giorni"
                  icon={Flame}
                  delay={100}
                  tooltip="Giorni consecutivi in cui hai ascoltato musica. Vai ai Pattern Temporali per i dettagli"
                  link="/temporal#streak"
                />
              </StaggerItem>
              {topGenre && (
                <StaggerItem>
                  <KPICard
                    title="Genere top"
                    value={topGenre}
                    suffix={topGenrePct ? ` (${topGenrePct}%)` : ''}
                    icon={Disc3}
                    delay={200}
                    tooltip="Il genere musicale più frequente tra i tuoi artisti"
                  />
                </StaggerItem>
              )}
              <StaggerItem>
                <KPICard
                  title="Artisti unici"
                  value={uniqueArtists}
                  icon={Users}
                  delay={300}
                  tooltip="Numero di artisti diversi tra i tuoi brani più ascoltati"
                />
              </StaggerItem>
            </StaggerContainer>

            {/* Trend Timeline — full width */}
            <TrendTimeline trends={trends} />

            {/* Radar + Top Tracks — 2 columns */}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
              <AudioRadar features={features} />

              <div className="glow-card bg-surface rounded-xl p-5">
                <h3 className="text-text-primary font-display font-semibold mb-4">
                  Top 50 Brani
                </h3>
                <div className="max-h-[600px] overflow-y-auto pr-1 space-y-1">
                  <StaggerContainer className="space-y-1">
                    {tracks.slice(0, 50).map((track, i) => (
                      <StaggerItem key={track.id}>
                        <TrackCard track={track} index={i} />
                      </StaggerItem>
                    ))}
                  </StaggerContainer>
                </div>
              </div>
            </div>

            {/* Genre Treemap + Export */}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
              <GenreTreemap genres={genres} />
              <ClaudeExportPanel />
            </div>
          </>
        )}
    </main>
  )
}
