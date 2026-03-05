import { useState } from 'react'
import { Disc3, Flame, Music, Users, Star, TrendingUp } from 'lucide-react'
import KPICard from '../components/cards/KPICard'
import TrackCard from '../components/cards/TrackCard'
import AudioRadar from '../components/charts/AudioRadar'
import TrendTimeline from '../components/charts/TrendTimeline'
import GenreTreemap from '../components/charts/GenreTreemap'
import ClaudeExportPanel from '../components/export/ClaudeExportPanel'
import PeriodSelector from '../components/ui/PeriodSelector'
import LoadingSpinner from '../components/ui/LoadingSpinner'
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

  const trackCount = topData?.total || tracks.length || 0

  // Popolarita' brani e artisti
  const trackPopularity = featuresData?.popularity_avg || 0
  const artistPopularity = featuresData?.artist_popularity_avg || 0

  // Streak di ascolto
  const currentStreak = temporalData?.streak?.current_streak || 0
  const maxStreak = temporalData?.streak?.max_streak || 0
  const activeDays = temporalData?.streak?.active_days || []

  // Artisti unici
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

  // Streak color scaling
  const streakColor = currentStreak === 0 ? 'text-text-muted'
    : currentStreak < 3 ? 'text-amber-400'
    : currentStreak < 7 ? 'text-orange-400'
    : 'text-red-400'

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
        <LoadingSpinner />
      ) : (
        <>
          {hasError && (
            <div className="text-red-400 text-sm bg-red-400/10 p-3 rounded-lg">
              Errore nel caricamento dei dati. Riprova tra qualche istante.
            </div>
          )}

          {/* KPI Row 1 */}
          <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-3 gap-4">
            <KPICard
              title="Brani analizzati"
              value={trackCount}
              icon={Music}
              delay={0}
              tooltip="Numero di brani nel tuo periodo di ascolto selezionato"
            />
            {trackPopularity > 0 && (
              <KPICard
                title="Pop. media brani"
                value={trackPopularity}
                suffix="/100"
                icon={TrendingUp}
                delay={100}
                tooltip="Popolarità media dei tuoi brani preferiti su Spotify (0 = nicchia, 100 = mainstream)"
              />
            )}
            {artistPopularity > 0 && (
              <KPICard
                title="Pop. media artisti"
                value={artistPopularity}
                suffix="/100"
                icon={Star}
                delay={150}
                tooltip="Popolarità media degli artisti che ascolti su Spotify (0 = nicchia, 100 = mainstream)"
              />
            )}
          </div>

          {/* KPI Row 2 */}
          <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-3 gap-4">
            {/* Streak KPI — addicting design */}
            <div
              className="glow-card bg-surface rounded-xl p-5 animate-slide-up relative overflow-hidden cursor-pointer hover:ring-1 hover:ring-accent/30 transition-all duration-300"
              style={{ animationDelay: '200ms', animationFillMode: 'both' }}
              onClick={() => { window.location.href = '/temporal#streak' }}
            >
              <div className="absolute left-0 top-0 bottom-0 w-[3px] bg-accent rounded-r-full" />
              <div className="flex items-start justify-between mb-2">
                <span className="text-text-secondary text-sm font-medium">Streak di ascolto</span>
                <div className={`w-8 h-8 rounded-lg bg-accent/10 flex items-center justify-center ${currentStreak > 0 ? 'animate-pulse' : ''}`}>
                  <Flame size={16} className={streakColor} />
                </div>
              </div>
              <div className="flex items-end gap-2">
                <span className={`text-4xl font-display font-bold ${streakColor}`}>
                  {currentStreak}
                </span>
                <span className="text-text-muted text-sm mb-1">giorni</span>
              </div>
              <div className="flex items-center gap-3 mt-2">
                <span className="text-text-muted text-xs">Record: {maxStreak} giorni</span>
                <div className="flex gap-0.5 ml-auto">
                  {activeDays.map((active, i) => (
                    <div
                      key={i}
                      className={`w-2.5 h-2.5 rounded-full transition-all ${
                        active ? 'bg-accent shadow-sm shadow-accent/30' : 'bg-surface-hover'
                      }`}
                      title={['Lun', 'Mar', 'Mer', 'Gio', 'Ven', 'Sab', 'Dom'][i]}
                    />
                  ))}
                </div>
              </div>
              {currentStreak === 0 && (
                <p className="text-amber-400/70 text-[10px] mt-1">Ascolta qualcosa per iniziare la streak!</p>
              )}
            </div>

            {topGenre && (
              <KPICard
                title="Genere top"
                value={topGenre}
                suffix={topGenrePct ? ` (${topGenrePct}%)` : ''}
                icon={Disc3}
                delay={250}
                tooltip="Il genere musicale più frequente tra i tuoi artisti"
              />
            )}
            <KPICard
              title="Artisti unici"
              value={uniqueArtists}
              icon={Users}
              delay={300}
              tooltip="Numero di artisti diversi tra i tuoi brani più ascoltati"
            />
          </div>

          {/* Trend Timeline */}
          <TrendTimeline trends={trends} />

          {/* Radar + Top Tracks */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            <AudioRadar features={features} />
            <div className="glow-card bg-surface rounded-xl p-5">
              <h3 className="text-text-primary font-display font-semibold mb-4">Top 50 Brani</h3>
              <div className="max-h-[600px] overflow-y-auto pr-1 space-y-1">
                {tracks.slice(0, 50).map((track, i) => (
                  <TrackCard key={track.id} track={track} index={i} />
                ))}
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
