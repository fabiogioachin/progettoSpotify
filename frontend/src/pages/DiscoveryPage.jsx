import { Compass, Sparkles, Star, BarChart3, Music } from 'lucide-react'
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
  const recommendations = discoveryData?.recommendations || []
  const outliers = discoveryData?.outliers || []
  const centroid = discoveryData?.centroid || {}
  const genreDistribution = discoveryData?.genre_distribution || {}
  const popularityDistribution = discoveryData?.popularity_distribution || []
  const hasAudioFeatures = discoveryData?.has_audio_features ?? false

  // Controlla se i tracks hanno features per il MoodScatter
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

            {/* Mood Scatter OPPURE Distribuzione Popolarita' */}
            {hasMoodData ? (
              <MoodScatter tracks={tracks} />
            ) : (
              <PopularityDistribution data={popularityDistribution} />
            )}

            {/* Genre Treemap + Centroid Radar o Outliers */}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
              {/* Se ci sono generi, mostra il treemap; altrimenti il radar se ha features */}
              {Object.keys(genreDistribution).length > 0 ? (
                <GenreTreemap genres={genreDistribution} title="Il tuo DNA musicale" />
              ) : (
                <AudioRadar features={centroid} title="Il tuo centro musicale" />
              )}

              <div className="glow-card bg-surface rounded-xl p-5">
                <h3 className="text-text-primary font-display font-semibold mb-4 flex items-center gap-2">
                  <Star size={18} className="text-amber-400" />
                  {hasAudioFeatures ? 'Brani Outlier' : 'Hidden Gems'}
                </h3>
                <p className="text-text-muted text-xs mb-3">
                  {hasAudioFeatures
                    ? 'Brani che si discostano dal tuo profilo medio'
                    : 'Brani meno conosciuti tra i tuoi preferiti'}
                </p>
                <div className="space-y-2">
                  {outliers.slice(0, 8).map((track) => (
                    <div
                      key={track.id}
                      className="flex items-center gap-3 p-2 rounded-lg hover:bg-surface-hover transition-all duration-300"
                    >
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
                      <span className="text-xs text-amber-400 bg-amber-400/10 px-2 py-0.5 rounded flex-shrink-0">
                        {track.metric_label || `${Math.round(track.distance * 100)}% diverso`}
                      </span>
                    </div>
                  ))}
                  {outliers.length === 0 && (
                    <p className="text-text-muted text-sm text-center py-4">
                      Nessun outlier trovato
                    </p>
                  )}
                </div>
              </div>
            </div>

            {/* Recommendations */}
            <div className="glow-card bg-surface rounded-xl p-5">
              <h3 className="text-text-primary font-display font-semibold mb-4 flex items-center gap-2">
                <Sparkles size={18} className="text-accent" />
                {recommendations.length > 0 ? 'Brani Suggeriti' : 'Scoperte Recenti'}
              </h3>
              <p className="text-text-muted text-xs mb-4">
                {recommendations.length > 0
                  ? 'Basati sul tuo profilo d\'ascolto — priorità ad artisti che non conosci ancora'
                  : 'Brani apparsi di recente nelle tue classifiche'}
              </p>
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-3">
                {recommendations.map((rec) => (
                  <div
                    key={rec.id}
                    className="flex items-start gap-3 p-3 rounded-lg bg-background hover:bg-surface-hover transition-all duration-300 group"
                  >
                    {rec.album_image ? (
                      <img
                        src={rec.album_image}
                        alt={rec.album}
                        className="w-12 h-12 rounded-md object-cover group-hover:scale-105 transition-transform"
                      />
                    ) : (
                      <div className="w-12 h-12 rounded-md bg-surface-hover flex items-center justify-center">
                        <Music size={18} className="text-text-muted" />
                      </div>
                    )}
                    <div className="flex-1 min-w-0">
                      <p className="text-text-primary text-sm font-medium truncate">
                        {rec.name}
                      </p>
                      <p className="text-text-muted text-xs truncate">{rec.artist}</p>
                      <div className="flex items-center gap-2 mt-1">
                        {rec.is_new_artist && (
                          <span className="text-[10px] text-accent bg-accent/10 px-1.5 py-0.5 rounded">
                            Nuovo artista
                          </span>
                        )}
                        {rec.popularity != null && (
                          <span className="text-[10px] text-text-muted">
                            Pop. {rec.popularity}
                          </span>
                        )}
                      </div>
                    </div>
                  </div>
                ))}
                {recommendations.length === 0 && (
                  <p className="text-text-muted text-sm col-span-full text-center py-8">
                    Nessun suggerimento disponibile
                  </p>
                )}
              </div>
            </div>
          </>
        )}
    </main>
  )
}

function PopularityDistribution({ data }) {
  if (!data || data.length === 0) {
    return (
      <div className="glow-card bg-surface rounded-xl p-5 flex items-center justify-center h-[300px]">
        <p className="text-text-muted text-sm">Nessun dato di popolarità disponibile</p>
      </div>
    )
  }

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
          <XAxis
            dataKey="range"
            tick={{ fill: '#b3b3b3', fontSize: 12 }}
            axisLine={{ stroke: '#282828' }}
          />
          <YAxis
            tick={{ fill: '#b3b3b3', fontSize: 12 }}
            axisLine={{ stroke: '#282828' }}
          />
          <Tooltip
            {...TOOLTIP_STYLE}
            formatter={(val) => [`${val} brani`, 'Conteggio']}
          />
          <Bar dataKey="count" fill="#6366f1" radius={[4, 4, 0, 0]} animationDuration={1500} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  )
}
