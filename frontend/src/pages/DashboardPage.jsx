import { useEffect, useState } from 'react'
import { Disc3, Flame, Music, Users } from 'lucide-react'
import KPICard from '../components/cards/KPICard'
import TrackCard from '../components/cards/TrackCard'
import AudioRadar from '../components/charts/AudioRadar'
import TrendTimeline from '../components/charts/TrendTimeline'
import GenreDonut from '../components/charts/GenreDonut'
import ClaudeExportPanel from '../components/export/ClaudeExportPanel'
import PeriodSelector from '../components/ui/PeriodSelector'
import { SkeletonKPICard, SkeletonCard } from '../components/ui/Skeleton'
import { StaggerContainer, StaggerItem } from '../components/ui/StaggerContainer'
import { useSpotifyData } from '../hooks/useSpotifyData'
import { useAudioAnalysis } from '../hooks/useAudioAnalysis'
import SectionErrorBoundary from '../components/ui/SectionErrorBoundary'
import { useAuth } from '../contexts/AuthContext'
import OnboardingModal from '../components/onboarding/OnboardingModal'

// Finestre esatte, contate sugli ascolti registrati. Spotify ne offre solo tre
// e diverse da queste (4 settimane, 6 mesi, tutti i tempi): stanno nella loro
// sezione, dove sono chiamate col loro nome.
const DASHBOARD_RANGES = [
  { value: '7d', label: '7gg' },
  { value: '30d', label: '1M' },
  { value: '90d', label: '3M' },
  { value: '1y', label: '1Y' },
  { value: 'all', label: 'Tutto' },
]

// Il periodo scelto governa anche i trend, che restano una vista di Spotify:
// qui si sceglie la finestra piu' vicina fra le tre che ha.
const RANGE_TO_SPOTIFY = {
  '7d': 'short_term',
  '30d': 'short_term',
  '90d': 'medium_term',
  '1y': 'long_term',
  'all': 'long_term',
}

const RANGE_LABEL = {
  '7d': 'ultimi 7 giorni',
  '30d': 'ultimo mese',
  '90d': 'ultimi 3 mesi',
  '1y': 'ultimo anno',
  'all': 'da sempre',
}

// Le uniche tre finestre che Spotify calcola, coi nomi che usa lui.
const SPOTIFY_RANGES = [
  { value: 'short_term', label: '4 settimane' },
  { value: 'medium_term', label: '6 mesi' },
  { value: 'long_term', label: 'Tutti i tempi' },
]

export default function DashboardPage() {
  const { user } = useAuth()
  const [showOnboarding, setShowOnboarding] = useState(
    user?.onboarding_completed === false &&
    localStorage.getItem('wrap_onboarding_dismissed') !== 'true'
  )
  const [range, setRange] = useState('30d')
  const [spotifyRange, setSpotifyRange] = useState('long_term')
  const spotifyPeriod = RANGE_TO_SPOTIFY[range]

  // Classifica di Spotify: resta, ma sui suoi periodi, che sono altri.
  const { data: topData, loading: topLoading, error: topError } = useSpotifyData(
    '/api/v1/library/top',
    { time_range: spotifyRange, limit: 50 }
  )

  // Classifica costruita sugli ascolti registrati: quante volte hai davvero
  // fatto partire ogni brano nel periodo scelto.
  const {
    data: playedData,
    loading: playedLoading,
    error: playedError,
    refetch: refetchPlayed,
  } = useSpotifyData('/api/v1/library/top-played', { range, limit: 50 })

  // Gli stessi brani, riordinati per quanto li ascolta il mondo. Segue il
  // periodo scelto in cima, perche' l'insieme di partenza sono i tuoi ascolti.
  const {
    data: globalPopularData,
    loading: globalPopularLoading,
  } = useSpotifyData('/api/v1/library/top-global-popular', { range, limit: 50 })

  // La classifica mondiale vera. Non prende `range`: nessuna fonte pubblica una
  // classifica mondiale "di tre mesi fa", quindi la card dichiara la sua data
  // invece di fingere di seguire il selettore in cima alla pagina.
  const {
    data: globalChartData,
    loading: globalChartLoading,
  } = useSpotifyData('/api/v1/library/top-global', { limit: 50 })

  // Le copertine mancanti arrivano in sottofondo, una chiamata per brano: si
  // richiede la lista finche' non sono tutte a posto, senza superare i due minuti.
  const pendingCovers = playedData?.images_pending || 0
  useEffect(() => {
    if (pendingCovers === 0) return
    let attempts = 0
    const id = setInterval(() => {
      attempts += 1
      if (attempts > 8) {
        clearInterval(id)
        return
      }
      refetchPlayed()
    }, 15000)
    return () => clearInterval(id)
  }, [pendingCovers, refetchPlayed])

  const { data: trendsData, loading: trendsLoading, error: trendsError } = useSpotifyData('/api/v1/analytics/trends')
  const { data: temporalData, loading: temporalLoading } = useSpotifyData('/api/v1/temporal', { range, tz: Intl.DateTimeFormat().resolvedOptions().timeZone })

  const tracks = topData?.tracks || []
  const trends = trendsData?.current || []

  // Le copertine arrivano dalla cache del backend; finche' non ci sono, si
  // riempiono con quelle della lista Spotify quando il brano compare in entrambe.
  const coverById = new Map(
    tracks.filter(t => t.album_image).map(t => [t.id, t.album_image])
  )
  const playedTracks = (playedData?.tracks || []).map(t => ({
    ...t,
    album_image: t.album_image || coverById.get(t.id) || null,
  }))

  const globalPopularTracks = (globalPopularData?.tracks || []).map(t => ({
    ...t,
    album_image: t.album_image || coverById.get(t.id) || null,
  }))
  // Card vuota = card nascosta. Il numero di colonne si conta sulle card che
  // hanno davvero dati: una griglia fissa lascerebbe un buco quando la
  // popolarita' non e' ancora in cache.
  const globalPopularMissing = globalPopularData?.popularity_missing || 0

  const globalChartTracks = globalChartData?.tracks || []
  // Card vuota = card nascosta: finche' la chiave Last.fm non c'e', o finche'
  // il primo rinfresco non e' arrivato, la card non occupa spazio.
  const showGlobalChart = globalChartLoading || globalChartTracks.length > 0
  const globalChartUpdatedAt = globalChartData?.updated_at
    ? new Date(globalChartData.updated_at).toLocaleDateString('it-IT', {
        day: 'numeric', month: 'long', year: 'numeric',
      })
    : null
  const showGlobalPopular = globalPopularLoading || globalPopularTracks.length > 0
  const rankingGridCols = showGlobalPopular
    ? 'grid-cols-1 lg:grid-cols-3'
    : 'grid-cols-1 lg:grid-cols-2'

  // Extract features/genres from trends for the selected period (avoids a separate API call)
  const periodProfile = trends.find(t => t.period === spotifyPeriod)
  const features = periodProfile?.features || {}
  const genres = periodProfile?.genres || {}
  const featuresLoading = trendsLoading

  // Audio analysis: trigger when no cached features but tracks exist
  const hasFeatures = Object.keys(features).length > 0
    && Object.entries(features).some(([k, v]) => k !== 'tempo' && v && v > 0)

  const {
    features: analysisFeatures,
    progress: analysisProgress,
    isAnalyzing,
  } = useAudioAnalysis(tracks, !hasFeatures && tracks.length > 0 && !trendsLoading)

  // Compute features to display: cached features OR computed from analysis results
  const displayFeatures = (() => {
    if (hasFeatures) return features
    if (Object.keys(analysisFeatures).length === 0) return features
    const featureKeys = ['energy', 'danceability', 'valence', 'acousticness', 'instrumentalness', 'speechiness', 'liveness']
    const avgs = {}
    featureKeys.forEach(key => {
      const vals = Object.values(analysisFeatures).map(f => f[key]).filter(v => v != null && v > 0)
      avgs[key] = vals.length ? Math.round(vals.reduce((a, b) => a + b, 0) / vals.length * 1000) / 1000 : 0
    })
    return avgs
  })()

  // KPI calculations — solo dati reali sempre disponibili
  const trackCount = playedData?.total || 0
  const playCount = playedData?.total_plays || 0

  // Streak di ascolto
  const streak = temporalData?.streak?.max_streak || 0

  // Artisti unici: preferisci backend, fallback dal conteggio tracks
  let uniqueArtists = periodProfile?.unique_artists || 0
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

  const hasError = topError || trendsError || playedError

  return (
    <>
    {showOnboarding && (
      <OnboardingModal onClose={() => setShowOnboarding(false)} />
    )}
    <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-6">
      {/* Header row */}
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-display font-bold text-text-primary">Dashboard</h1>
          <p className="text-text-secondary text-sm">Panoramica del tuo profilo musicale</p>
        </div>
        <PeriodSelector value={range} onChange={setRange} options={DASHBOARD_RANGES} />
      </div>

      {hasError && (
        <div className="text-red-400 text-sm bg-red-400/10 p-3 rounded-lg">
          Errore nel caricamento dei dati. Riprova tra qualche istante.
        </div>
      )}

      {/* KPI Row — each card renders independently with per-section skeleton */}
      <SectionErrorBoundary sectionName="KPICards">
        <StaggerContainer className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-4">
          <StaggerItem>
            {playedLoading ? <SkeletonKPICard /> : (
              <KPICard
                title="Brani ascoltati"
                value={trackCount}
                icon={Music}
                delay={0}
                tooltip={`Brani diversi che hai ascoltato ${RANGE_LABEL[range]}, su ${playCount} ascolti in tutto. Scorri in basso per la classifica`}
                link="#top-tracks"
              />
            )}
          </StaggerItem>
          <StaggerItem>
            {temporalLoading ? <SkeletonKPICard /> : (
              <KPICard
                title="Streak di ascolto"
                value={streak}
                suffix=" giorni"
                icon={Flame}
                delay={100}
                tooltip="Giorni consecutivi in cui hai ascoltato musica. Vai ai Pattern Temporali per i dettagli"
                link="/temporal#streak"
              />
            )}
          </StaggerItem>
          {(featuresLoading || topGenre) && (
            <StaggerItem>
              {featuresLoading ? <SkeletonKPICard /> : (
                <KPICard
                  title="Genere top"
                  value={topGenre}
                  suffix={topGenrePct ? ` (${topGenrePct}%)` : ''}
                  icon={Disc3}
                  delay={200}
                  tooltip="Il genere musicale più frequente tra i tuoi artisti"
                />
              )}
            </StaggerItem>
          )}
          <StaggerItem>
            {featuresLoading ? <SkeletonKPICard /> : (
              <KPICard
                title="Artisti unici"
                value={uniqueArtists}
                icon={Users}
                delay={300}
                tooltip="Artisti distinti estratti dai tuoi brani più ascoltati nel periodo selezionato"
                link="/artists"
              />
            )}
          </StaggerItem>
        </StaggerContainer>
      </SectionErrorBoundary>

      {/* Trend Timeline — shows independently */}
      <SectionErrorBoundary sectionName="TrendTimeline">
        {trendsLoading ? (
          <SkeletonCard height="h-48" />
        ) : (
          <TrendTimeline
            trends={trends}
            dailyMinutes={temporalData?.daily_minutes}
            temporalRange={range}
          />
        )}
      </SectionErrorBoundary>

      {/* Radar + le due classifiche — colonne contate sulle card con dati */}
      <div className={`grid ${rankingGridCols} gap-4`}>
        <SectionErrorBoundary sectionName="AudioRadar">
          {featuresLoading ? (
            <SkeletonCard height="h-72" />
          ) : isAnalyzing ? (
            <div className="glow-card bg-surface rounded-xl p-5 flex flex-col items-center justify-center h-72">
              <div className="text-text-primary font-display font-semibold mb-2">Analisi audio in corso...</div>
              <div className="w-48 h-2 bg-surface-hover rounded-full overflow-hidden mb-2">
                <div
                  className="h-full bg-accent rounded-full transition-all duration-500"
                  style={{ width: `${analysisProgress.percent}%` }}
                />
              </div>
              <p className="text-text-muted text-xs">
                {analysisProgress.completed}/{analysisProgress.total} brani
              </p>
            </div>
          ) : (
            <AudioRadar features={displayFeatures} />
          )}
        </SectionErrorBoundary>

        <SectionErrorBoundary sectionName="TopPlayed">
          {playedLoading ? (
            <SkeletonCard height="h-72" />
          ) : (
            <div id="top-tracks" className="glow-card bg-surface rounded-xl p-5">
              <h3 className="text-text-primary font-display font-semibold">
                I tuoi brani più ascoltati
              </h3>
              <p className="text-text-muted text-xs mb-4">
                Contati dai tuoi ascolti registrati, {RANGE_LABEL[range]}
                {playCount > 0 && ` · ${playCount} ascolti`}
                {pendingCovers > 0 && ` · recupero ${pendingCovers} copertine…`}
              </p>
              {playedTracks.length === 0 ? (
                <p className="text-text-secondary text-sm">
                  Nessun ascolto registrato in questo periodo.
                </p>
              ) : (
                <div className="max-h-[600px] overflow-y-auto pr-1 space-y-1">
                  <StaggerContainer className="space-y-1">
                    {playedTracks.map((track, i) => (
                      <StaggerItem key={track.id}>
                        <TrackCard track={track} index={i} />
                      </StaggerItem>
                    ))}
                  </StaggerContainer>
                </div>
              )}
            </div>
          )}
        </SectionErrorBoundary>

        {showGlobalPopular && (
          <SectionErrorBoundary sectionName="TopGlobalPopular">
            {globalPopularLoading ? (
              <SkeletonCard height="h-72" />
            ) : (
              <div id="top-global-popular" className="glow-card bg-surface rounded-xl p-5">
                <h3 className="text-text-primary font-display font-semibold">
                  Popolari nel mondo, fra i tuoi
                </h3>
                <p className="text-text-muted text-xs mb-4">
                  I tuoi brani {RANGE_LABEL[range]}, ordinati per quanto li ascolta
                  il mondo secondo Last.fm
                  {globalPopularMissing > 0 && ` · ${globalPopularMissing} senza dato, esclusi`}
                </p>
                <div className="max-h-[600px] overflow-y-auto pr-1 space-y-1">
                  <StaggerContainer className="space-y-1">
                    {globalPopularTracks.map((track, i) => (
                      <StaggerItem key={track.id}>
                        <TrackCard track={track} index={i} />
                      </StaggerItem>
                    ))}
                  </StaggerContainer>
                </div>
              </div>
            )}
          </SectionErrorBoundary>
        )}
      </div>

      {/* Classifica mondiale — non segue il periodo, e lo dichiara */}
      {showGlobalChart && (
        <SectionErrorBoundary sectionName="TopGlobal">
          {globalChartLoading ? (
            <SkeletonCard height="h-72" />
          ) : (
            <div id="top-global" className="glow-card bg-surface rounded-xl p-5">
              <h3 className="text-text-primary font-display font-semibold">
                I brani più ascoltati nel mondo
              </h3>
              <p className="text-text-muted text-xs mb-4">
                La classifica mondiale di Last.fm
                {globalChartUpdatedAt && `, aggiornata al ${globalChartUpdatedAt}`}.
                Non segue il periodo scelto in cima alla pagina: una classifica
                mondiale esiste solo al presente.
              </p>
              <div className="max-h-[600px] overflow-y-auto pr-1 space-y-1">
                <StaggerContainer className="space-y-1">
                  {globalChartTracks.map((track, i) => (
                    <StaggerItem key={`${track.rank}-${track.name}`}>
                      <TrackCard
                        track={{
                          name: track.name,
                          artist: track.artist,
                          album_image: track.image,
                        }}
                        index={i}
                      />
                    </StaggerItem>
                  ))}
                </StaggerContainer>
              </div>
            </div>
          )}
        </SectionErrorBoundary>
      )}

      {/* Classifica di Spotify — periodo suo, non quello scelto sopra */}
      <SectionErrorBoundary sectionName="TopTracks">
        {topLoading ? (
          <SkeletonCard height="h-72" />
        ) : tracks.length > 0 && (
          <div id="top-tracks-spotify" className="glow-card bg-surface rounded-xl p-5">
            <div className="flex flex-col sm:flex-row sm:items-start sm:justify-between gap-3">
              <div>
                <h3 className="text-text-primary font-display font-semibold">
                  Top 50 secondo Spotify
                </h3>
                <p className="text-text-muted text-xs mb-4">
                  La classifica che Spotify calcola <strong>per te</strong>: e' personale,
                  non mondiale. Non conta gli ascolti uno per uno, e ha solo queste tre
                  finestre: per questo non segue il periodo scelto in cima alla pagina.
                </p>
              </div>
              <PeriodSelector
                value={spotifyRange}
                onChange={setSpotifyRange}
                options={SPOTIFY_RANGES}
              />
            </div>
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
        )}
      </SectionErrorBoundary>

      {/* Genre Donut + Export */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <SectionErrorBoundary sectionName="GenreDonut">
          {featuresLoading ? (
            <SkeletonCard height="h-72" />
          ) : (
            <GenreDonut genres={genres} />
          )}
        </SectionErrorBoundary>
        <SectionErrorBoundary sectionName="ClaudeExportPanel">
          <ClaudeExportPanel />
        </SectionErrorBoundary>
      </div>
    </main>
    </>
  )
}
