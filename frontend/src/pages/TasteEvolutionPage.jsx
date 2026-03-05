import { useSpotifyData } from '../hooks/useSpotifyData'
import KPICard from '../components/cards/KPICard'
import TasteOverlapBar from '../components/charts/TasteOverlapBar'
import LoadingSpinner from '../components/ui/LoadingSpinner'
import TrackCard from '../components/cards/TrackCard'
import { Heart, TrendingUp, TrendingDown, Users, Music, RefreshCw, Calendar, ChevronDown, ChevronUp } from 'lucide-react'
import { useState } from 'react'

export default function TasteEvolutionPage() {
  const { data, loading, error, refetch } = useSpotifyData('/api/taste-evolution')
  const { data: historicalData, loading: histLoading } = useSpotifyData('/api/historical-tops')
  const [expandedYear, setExpandedYear] = useState(null)

  const metrics = data?.metrics || {}
  const artists = data?.artists || {}
  const tracks = data?.tracks || {}
  const overlapData = data?.overlap_distribution || []

  const years = historicalData?.years || []

  return (
    <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-6">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-display font-bold text-text-primary">Evoluzione del Gusto</h1>
            <p className="text-text-secondary text-sm mt-1">Come cambia il tuo gusto musicale nel tempo</p>
          </div>
          <button onClick={() => refetch()} className="p-2 rounded-lg text-text-muted hover:text-text-primary hover:bg-surface-hover transition-all duration-300" title="Aggiorna">
            <RefreshCw size={18} />
          </button>
        </div>

        {error && (
          <div className="bg-red-500/10 border border-red-500/20 rounded-xl p-4 text-red-400 text-sm">{error}</div>
        )}

        {loading ? (
          <LoadingSpinner />
        ) : (
          <>
            {/* KPI Cards */}
            <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-4">
              <KPICard title="Fedeltà" value={metrics.loyalty_score || 0} suffix="%" icon={Heart} delay={0} tooltip="Percentuale di artisti che ascolti stabilmente in più periodi" />
              <KPICard title="Turnover" value={metrics.turnover_rate || 0} suffix="%" icon={RefreshCw} delay={100} tooltip="Percentuale di artisti nuovi rispetto al periodo precedente" />
              <KPICard title="Artisti Fedeli" value={(artists.loyal || []).length} icon={Users} delay={200} tooltip="Artisti presenti nelle tue classifiche in tutti e tre i periodi" />
              <KPICard title="Tracce Persistenti" value={metrics.persistent_tracks_count || 0} icon={Music} delay={300} tooltip="Brani che restano tra i tuoi preferiti in più periodi temporali" />
            </div>

            {/* Overlap Distribution */}
            <TasteOverlapBar data={overlapData} />

            {/* Artist Sections */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              <ArtistColumn title="In Ascesa" icon={TrendingUp} iconColor="text-emerald-400" artists={artists.rising || []} emptyText="Nessun nuovo artista" />
              <ArtistColumn title="Sempre Fedeli" icon={Heart} iconColor="text-accent" artists={artists.loyal || []} emptyText="Nessun artista fedele" />
              <ArtistColumn title="In Calo" icon={TrendingDown} iconColor="text-red-400" artists={artists.falling || []} emptyText="Nessun artista in calo" />
            </div>

            {/* Persistent Tracks */}
            {(tracks.persistent || []).length > 0 && (
              <div className="glow-card bg-surface rounded-xl p-5">
                <h3 className="text-text-primary font-display font-semibold mb-4 flex items-center gap-2">
                  <Music size={18} className="text-accent" />
                  Tracce che ascolti sempre
                </h3>
                <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-3">
                  {tracks.persistent.map((track, i) => (
                    <div key={track.id} className="flex items-center gap-3 p-2 rounded-lg hover:bg-surface-hover transition-all duration-300 animate-slide-up" style={{ animationDelay: `${i * 50}ms` }}>
                      {track.album_image ? (
                        <img src={track.album_image} alt={track.name} className="w-10 h-10 rounded object-cover flex-shrink-0" />
                      ) : (
                        <div className="w-10 h-10 rounded bg-surface-hover flex items-center justify-center flex-shrink-0">
                          <Music size={16} className="text-text-muted" />
                        </div>
                      )}
                      <div className="min-w-0">
                        <p className="text-text-primary text-sm font-medium truncate">{track.name}</p>
                        <p className="text-text-muted text-xs truncate">{track.artist}</p>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Rising Tracks */}
            {(tracks.rising || []).length > 0 && (
              <div className="glow-card bg-surface rounded-xl p-5">
                <h3 className="text-text-primary font-display font-semibold mb-4 flex items-center gap-2">
                  <TrendingUp size={18} className="text-emerald-400" />
                  Nuove scoperte
                </h3>
                <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-3">
                  {tracks.rising.slice(0, 10).map((track, i) => (
                    <div key={track.id} className="flex items-center gap-3 p-2 rounded-lg hover:bg-surface-hover transition-all duration-300 animate-slide-up" style={{ animationDelay: `${i * 50}ms` }}>
                      {track.album_image ? (
                        <img src={track.album_image} alt={track.name} className="w-10 h-10 rounded object-cover flex-shrink-0" />
                      ) : (
                        <div className="w-10 h-10 rounded bg-surface-hover flex items-center justify-center flex-shrink-0">
                          <Music size={16} className="text-text-muted" />
                        </div>
                      )}
                      <div className="min-w-0">
                        <p className="text-text-primary text-sm font-medium truncate">{track.name}</p>
                        <p className="text-text-muted text-xs truncate">{track.artist}</p>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Historical Yearly Section */}
            <div className="glow-card bg-surface rounded-xl p-5">
              <h3 className="text-text-primary font-display font-semibold mb-4 flex items-center gap-2">
                <Calendar size={18} className="text-spotify" />
                Il Tuo Viaggio Musicale
                {years.length > 0 && (
                  <span className="text-text-muted text-xs font-normal ml-auto">{years.length} anni</span>
                )}
              </h3>

              {histLoading ? (
                <LoadingSpinner size="sm" />
              ) : years.length === 0 ? (
                <div className="text-center py-8">
                  <Calendar size={32} className="text-text-muted mx-auto mb-3" />
                  <p className="text-text-secondary text-sm">
                    Le playlist "Your Top Songs" di Spotify Wrapped appariranno qui
                  </p>
                  <p className="text-text-muted text-xs mt-1">
                    Spotify genera automaticamente queste playlist ogni dicembre
                  </p>
                </div>
              ) : (
                <div className="space-y-3">
                  {/* Timeline */}
                  <div className="flex items-center gap-2 overflow-x-auto pb-2">
                    {years.map((y, i) => (
                      <button
                        key={y.year}
                        onClick={() => setExpandedYear(expandedYear === y.year ? null : y.year)}
                        className={`flex-shrink-0 px-4 py-2 rounded-lg text-sm font-medium transition-all duration-300 ${
                          expandedYear === y.year
                            ? 'bg-spotify text-white'
                            : 'bg-surface-hover text-text-secondary hover:text-text-primary'
                        }`}
                      >
                        {y.year}
                        <span className="text-xs ml-1 opacity-70">{y.track_count} brani</span>
                      </button>
                    ))}
                  </div>

                  {/* Expanded year tracks */}
                  {expandedYear && (() => {
                    const yearData = years.find(y => y.year === expandedYear)
                    if (!yearData) return null
                    return (
                      <div className="animate-slide-up">
                        <div className="flex items-center gap-3 mb-3">
                          <h4 className="text-text-primary font-display font-semibold text-lg">
                            Top Songs {yearData.year}
                          </h4>
                          <span className="text-text-muted text-xs">{yearData.track_count} brani</span>
                          <button
                            onClick={() => setExpandedYear(null)}
                            className="ml-auto text-text-muted hover:text-text-primary transition-colors"
                          >
                            <ChevronUp size={16} />
                          </button>
                        </div>
                        <div className="space-y-1 max-h-[400px] overflow-y-auto pr-1">
                          {yearData.tracks.slice(0, 50).map((track, i) => (
                            <TrackCard
                              key={`${yearData.year}-${i}`}
                              track={{
                                id: `hist-${yearData.year}-${i}`,
                                name: track.name,
                                artist: track.artist,
                                album: track.album,
                                album_image: track.album_image,
                              }}
                              index={i}
                            />
                          ))}
                        </div>
                      </div>
                    )
                  })()}

                  {/* Summary when no year expanded */}
                  {!expandedYear && (
                    <p className="text-text-muted text-xs">
                      Clicca su un anno per vedere i brani piu ascoltati
                    </p>
                  )}
                </div>
              )}
            </div>
          </>
        )}
      </main>
  )
}

function ArtistColumn({ title, icon: Icon, iconColor, artists, emptyText }) {
  return (
    <div className="glow-card bg-surface rounded-xl p-5">
      <h3 className="text-text-primary font-display font-semibold mb-4 flex items-center gap-2">
        <Icon size={18} className={iconColor} />
        {title}
        <span className="text-text-muted text-xs font-normal ml-auto">{artists.length}</span>
      </h3>
      {artists.length === 0 ? (
        <p className="text-text-muted text-sm text-center py-4">{emptyText}</p>
      ) : (
        <div className="space-y-2 max-h-80 overflow-y-auto">
          {artists.map((artist, i) => (
            <div key={artist.id} className="flex items-center gap-3 p-2 rounded-lg hover:bg-surface-hover transition-all duration-300 animate-slide-up" style={{ animationDelay: `${i * 50}ms` }}>
              {artist.image ? (
                <img src={artist.image} alt={artist.name} className="w-10 h-10 rounded-full object-cover flex-shrink-0" />
              ) : (
                <div className="w-10 h-10 rounded-full bg-surface-hover flex items-center justify-center flex-shrink-0">
                  <Users size={16} className="text-text-muted" />
                </div>
              )}
              <span className="text-text-primary text-sm truncate">{artist.name}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
