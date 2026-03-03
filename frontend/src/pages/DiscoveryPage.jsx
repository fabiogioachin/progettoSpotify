import { Compass, Sparkles, Star } from 'lucide-react'
import Header from '../components/layout/Header'
import MoodScatter from '../components/charts/MoodScatter'
import AudioRadar from '../components/charts/AudioRadar'
import LoadingSpinner from '../components/ui/LoadingSpinner'
import { useSpotifyData } from '../hooks/useSpotifyData'

export default function DiscoveryPage() {
  const { data: topData, loading: topLoading, error: topError } = useSpotifyData('/api/library/top', { limit: 50 })
  const { data: discoveryData, loading: discoveryLoading, error: discoveryError } = useSpotifyData('/api/analytics/discovery')

  const tracks = topData?.tracks || []
  const recommendations = discoveryData?.recommendations || []
  const outliers = discoveryData?.outliers || []
  const centroid = discoveryData?.centroid || {}

  const isLoading = topLoading || discoveryLoading
  const hasError = topError || discoveryError

  return (
    <div className="min-h-screen bg-background">
      <Header />

      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6 space-y-6">
        <div>
          <h1 className="text-2xl font-display font-bold text-text-primary flex items-center gap-2">
            <Compass size={24} className="text-accent" />
            Discovery
          </h1>
          <p className="text-text-muted text-sm">
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

            {/* Mood Scatter — full width */}
            <MoodScatter tracks={tracks} />

            {/* Centroid Radar + Outliers */}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
              <AudioRadar features={centroid} title="Il tuo centro musicale" />

              <div className="glow-card bg-surface rounded-xl p-5">
                <h3 className="text-text-primary font-display font-semibold mb-4 flex items-center gap-2">
                  <Star size={18} className="text-amber-400" />
                  Brani Outlier
                </h3>
                <p className="text-text-muted text-xs mb-3">
                  Brani che si discostano dal tuo profilo medio
                </p>
                <div className="space-y-2">
                  {outliers.slice(0, 8).map((track) => (
                    <div
                      key={track.id}
                      className="flex items-center gap-3 p-2 rounded-lg hover:bg-surface-hover transition-all duration-300"
                    >
                      <div className="flex-1 min-w-0">
                        <p className="text-text-primary text-sm truncate">{track.name}</p>
                        <p className="text-text-muted text-xs truncate">{track.artist}</p>
                      </div>
                      <span className="text-xs text-amber-400 bg-amber-400/10 px-2 py-0.5 rounded">
                        {Math.round(track.distance * 100)}% diverso
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
                Brani Suggeriti
              </h3>
              <p className="text-text-muted text-xs mb-4">
                Basati sul tuo profilo d'ascolto — priorità ad artisti che non conosci ancora
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
                      <div className="w-12 h-12 rounded-md bg-surface-hover" />
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
                        {rec.distance_from_profile != null && (
                          <span className="text-[10px] text-text-muted">
                            {Math.round(rec.distance_from_profile * 100)}% dist.
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
    </div>
  )
}
