import { Compass, Sparkles, Star, BarChart3, Music, TrendingUp, Users } from 'lucide-react'
import MoodScatter from '../components/charts/MoodScatter'
import AudioRadar from '../components/charts/AudioRadar'
import GenreTreemap from '../components/charts/GenreTreemap'
import LoadingSpinner from '../components/ui/LoadingSpinner'
import { useSpotifyData } from '../hooks/useSpotifyData'
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts'
import { TOOLTIP_STYLE } from '../lib/chartTheme'

export default function DiscoveryPage() {
  const { data: topData, loading: topLoading, error: topError } = useSpotifyData('/api/library/top', { limit: 50 })
  const { data: discoveryData, loading: discoveryLoading, error: discoveryError } = useSpotifyData('/api/analytics/discovery')

  const tracks = topData?.tracks || []
  const hiddenGems = discoveryData?.hidden_gems || []
  const newDiscoveries = discoveryData?.new_discoveries || []
  const relatedSuggestions = discoveryData?.related_suggestions || []
  const recommendations = discoveryData?.recommendations || []
  const centroid = discoveryData?.centroid || {}
  const genreDistribution = discoveryData?.genre_distribution || {}
  const popularityDistribution = discoveryData?.popularity_distribution || []
  const hasAudioFeatures = discoveryData?.has_audio_features ?? false
  const recommendationsSource = discoveryData?.recommendations_source || 'spotify'

  const tracksWithFeatures = tracks.filter(t => t.features && Object.values(t.features).some(v => v > 0))
  const hasMoodData = tracksWithFeatures.length > 0

  const isLoading = topLoading || discoveryLoading
  const hasError = topError || discoveryError

  return (
    <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-6">
      <div>
        <h1 className="text-2xl font-display font-bold text-text-primary flex items-center gap-2">
          <Compass size={24} className="text-accent" />
          Discovery
        </h1>
        <p className="text-text-secondary text-sm">
          Esplora la tua mappa musicale e scopri nuovi artisti
        </p>
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

          {/* Distribuzione Popolarita' — sempre visibile */}
          <PopularityDistribution data={popularityDistribution} />

          {/* Mood Scatter se audio features disponibili */}
          {hasMoodData && <MoodScatter tracks={tracks} />}

          {/* Genre Treemap + Chicche Nascoste */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            {Object.keys(genreDistribution).length > 0 ? (
              <GenreTreemap genres={genreDistribution} title="Il tuo DNA musicale" />
            ) : (
              hasAudioFeatures && Object.keys(centroid).length > 0 && (
                <AudioRadar features={centroid} title="Il tuo centro musicale" />
              )
            )}

            {hiddenGems.length > 0 && (
              <div className="glow-card bg-surface rounded-xl p-5">
                <h3 className="text-text-primary font-display font-semibold mb-4 flex items-center gap-2">
                  <Star size={18} className="text-amber-400" />
                  Chicche Nascoste
                </h3>
                <p className="text-text-muted text-xs mb-3">
                  Il 25% meno popolare tra i tuoi brani preferiti — le tue gemme personali
                </p>
                <div className="space-y-2">
                  {hiddenGems.slice(0, 8).map((track) => (
                    <TrackRow key={track.id} track={track} badge={track.metric_label} badgeColor="text-amber-400 bg-amber-400/10" />
                  ))}
                </div>
              </div>
            )}
          </div>

          {/* Scoperte Recenti */}
          {newDiscoveries.length > 0 && (
            <div className="glow-card bg-surface rounded-xl p-5">
              <h3 className="text-text-primary font-display font-semibold mb-4 flex items-center gap-2">
                <TrendingUp size={18} className="text-emerald-400" />
                Scoperte Recenti
              </h3>
              <p className="text-text-muted text-xs mb-4">
                Brani apparsi di recente nelle tue classifiche — non ancora nel tuo medio termine
              </p>
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-5 gap-3">
                {newDiscoveries.map((rec) => (
                  <CompactTrackCard key={rec.id} track={rec} />
                ))}
              </div>
            </div>
          )}

          {/* Da Artisti Simili */}
          {relatedSuggestions.length > 0 && (
            <div className="glow-card bg-surface rounded-xl p-5">
              <h3 className="text-text-primary font-display font-semibold mb-4 flex items-center gap-2">
                <Users size={18} className="text-accent" />
                Da Artisti Simili
              </h3>
              <p className="text-text-muted text-xs mb-4">
                Brani di artisti correlati ai tuoi preferiti che non ascolti ancora
              </p>
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-3">
                {relatedSuggestions.map((rec) => (
                  <div key={rec.id} className="flex items-start gap-3 p-3 rounded-lg bg-background hover:bg-surface-hover transition-all duration-300 group">
                    {rec.album_image ? (
                      <img src={rec.album_image} alt={rec.album} className="w-12 h-12 rounded-md object-cover group-hover:scale-105 transition-transform" />
                    ) : (
                      <div className="w-12 h-12 rounded-md bg-surface-hover flex items-center justify-center">
                        <Music size={18} className="text-text-muted" />
                      </div>
                    )}
                    <div className="flex-1 min-w-0">
                      <p className="text-text-primary text-sm font-medium truncate">{rec.name}</p>
                      <p className="text-text-muted text-xs truncate">{rec.artist}</p>
                      <div className="flex items-center gap-2 mt-1">
                        {rec.related_to && (
                          <span className="text-[10px] text-accent bg-accent/10 px-1.5 py-0.5 rounded truncate max-w-[120px]">
                            Simile a {rec.related_to}
                          </span>
                        )}
                        {rec.popularity != null && (
                          <span className="text-[10px] text-text-muted">Pop. {rec.popularity}</span>
                        )}
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Recommendations (Spotify API o fallback) */}
          {recommendations.length > 0 && (
            <div className="glow-card bg-surface rounded-xl p-5">
              <h3 className="text-text-primary font-display font-semibold mb-4 flex items-center gap-2">
                <Sparkles size={18} className="text-accent" />
                {recommendationsSource === 'spotify' ? 'Brani Suggeriti' : 'Altre Scoperte'}
              </h3>
              <p className="text-text-muted text-xs mb-4">
                {recommendationsSource === 'spotify'
                  ? "Basati sul tuo profilo d'ascolto — priorità ad artisti che non conosci ancora"
                  : 'Brani apparsi di recente nelle tue classifiche'}
              </p>
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-3">
                {recommendations.map((rec) => (
                  <div key={rec.id} className="flex items-start gap-3 p-3 rounded-lg bg-background hover:bg-surface-hover transition-all duration-300 group">
                    {rec.album_image ? (
                      <img src={rec.album_image} alt={rec.album} className="w-12 h-12 rounded-md object-cover group-hover:scale-105 transition-transform" />
                    ) : (
                      <div className="w-12 h-12 rounded-md bg-surface-hover flex items-center justify-center">
                        <Music size={18} className="text-text-muted" />
                      </div>
                    )}
                    <div className="flex-1 min-w-0">
                      <p className="text-text-primary text-sm font-medium truncate">{rec.name}</p>
                      <p className="text-text-muted text-xs truncate">{rec.artist}</p>
                      <div className="flex items-center gap-2 mt-1">
                        {rec.is_new_artist && (
                          <span className="text-[10px] text-accent bg-accent/10 px-1.5 py-0.5 rounded">Nuovo artista</span>
                        )}
                        {rec.popularity != null && (
                          <span className="text-[10px] text-text-muted">Pop. {rec.popularity}</span>
                        )}
                      </div>
                    </div>
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

function TrackRow({ track, badge, badgeColor = 'text-amber-400 bg-amber-400/10' }) {
  return (
    <div className="flex items-center gap-3 p-2 rounded-lg hover:bg-surface-hover transition-all duration-300">
      {track.album_image ? (
        <img src={track.album_image} alt={track.name} className="w-10 h-10 rounded object-cover flex-shrink-0" />
      ) : (
        <div className="w-10 h-10 rounded bg-surface-hover flex items-center justify-center flex-shrink-0">
          <Music size={16} className="text-text-muted" />
        </div>
      )}
      <div className="flex-1 min-w-0">
        <p className="text-text-primary text-sm truncate">{track.name}</p>
        <p className="text-text-muted text-xs truncate">{track.artist}</p>
      </div>
      {badge && (
        <span className={`text-xs ${badgeColor} px-2 py-0.5 rounded flex-shrink-0`}>{badge}</span>
      )}
    </div>
  )
}

function CompactTrackCard({ track }) {
  return (
    <div className="flex items-center gap-3 p-2 rounded-lg bg-background hover:bg-surface-hover transition-all duration-300">
      {track.album_image ? (
        <img src={track.album_image} alt={track.name} className="w-10 h-10 rounded object-cover flex-shrink-0" />
      ) : (
        <div className="w-10 h-10 rounded bg-surface-hover flex items-center justify-center flex-shrink-0">
          <Music size={16} className="text-text-muted" />
        </div>
      )}
      <div className="min-w-0 flex-1">
        <p className="text-text-primary text-xs font-medium truncate">{track.name}</p>
        <p className="text-text-muted text-[10px] truncate">{track.artist}</p>
      </div>
    </div>
  )
}

function PopularityDistribution({ data }) {
  if (!data || data.length === 0) return null
  return (
    <div className="glow-card bg-surface rounded-xl p-5">
      <h3 className="text-text-primary font-display font-semibold mb-1 flex items-center gap-2">
        <BarChart3 size={18} className="text-accent" />
        Distribuzione Popolarità
      </h3>
      <p className="text-text-muted text-xs mb-4">
        Come si distribuisce la popolarità dei tuoi brani preferiti (0 = nicchia, 100 = mainstream)
      </p>
      <ResponsiveContainer width="100%" height={280}>
        <BarChart data={data} margin={{ top: 5, right: 20, left: 0, bottom: 5 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#282828" />
          <XAxis dataKey="range" tick={{ fill: '#b3b3b3', fontSize: 12 }} axisLine={{ stroke: '#282828' }} />
          <YAxis tick={{ fill: '#b3b3b3', fontSize: 12 }} axisLine={{ stroke: '#282828' }} />
          <Tooltip {...TOOLTIP_STYLE} formatter={(val) => [`${val} brani`, 'Conteggio']} />
          <Bar dataKey="count" fill="#6366f1" radius={[4, 4, 0, 0]} animationDuration={1500} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  )
}
