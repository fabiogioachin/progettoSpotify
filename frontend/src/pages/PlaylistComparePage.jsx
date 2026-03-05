import { useState, useEffect } from 'react'
import { ListMusic, Music, BarChart3 } from 'lucide-react'
import PlaylistComparison from '../components/charts/PlaylistComparison'
import AudioRadar from '../components/charts/AudioRadar'
import LoadingSpinner from '../components/ui/LoadingSpinner'
import { useSpotifyData } from '../hooks/useSpotifyData'
import { usePlaylistCompare } from '../hooks/usePlaylistCompare'

export default function PlaylistComparePage() {
  const { data: playlistsData, loading: playlistsLoading } = useSpotifyData('/api/playlists')

  const [selectedIds, setSelectedIds] = useState([])
  const { data: comparison, loading: comparing, error: compareError, compare, reset } = usePlaylistCompare()

  // Reset stale comparison when selection changes
  useEffect(() => {
    if (comparison) reset()
  }, [selectedIds.length]) // eslint-disable-line react-hooks/exhaustive-deps

  const playlists = playlistsData?.playlists || []

  function togglePlaylist(id) {
    setSelectedIds((prev) => {
      if (prev.includes(id)) return prev.filter((p) => p !== id)
      if (prev.length >= 4) return prev
      return [...prev, id]
    })
  }

  function handleCompare() {
    compare(selectedIds)
  }

  const playlistNames = {}
  const playlistImages = {}
  playlists.forEach((p) => {
    playlistNames[p.id] = p.name
    playlistImages[p.id] = p.image
  })

  return (
    <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-6">
        <div>
          <h1 className="text-2xl font-display font-bold text-text-primary">
            Confronto Playlist
          </h1>
          <p className="text-text-secondary text-sm">
            Seleziona da 2 a 4 playlist per confrontare profili, brani e generi
          </p>
        </div>

        {playlistsLoading ? (
          <LoadingSpinner />
        ) : (
          <>
            {/* Playlist selector */}
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-3">
              {playlists.map((p) => {
                const isSelected = selectedIds.includes(p.id)
                return (
                  <button
                    key={p.id}
                    onClick={() => togglePlaylist(p.id)}
                    className={`flex items-center gap-3 p-3 rounded-xl text-left transition-all duration-300
                      ${isSelected
                        ? 'bg-accent/10 border-2 border-accent shadow-lg shadow-accent/10'
                        : 'glow-card bg-surface hover:bg-surface-hover'
                      }`}
                  >
                    {p.image ? (
                      <img src={p.image} alt={p.name} className="w-12 h-12 rounded-lg object-cover" />
                    ) : (
                      <div className="w-12 h-12 rounded-lg bg-surface-hover flex items-center justify-center">
                        <ListMusic size={20} className="text-text-muted" />
                      </div>
                    )}
                    <div className="flex-1 min-w-0">
                      <p className="text-text-primary text-sm font-medium truncate">{p.name}</p>
                      <p className="text-text-muted text-xs">{p.track_count} brani</p>
                    </div>
                    {isSelected && (
                      <div className="w-6 h-6 rounded-full bg-accent flex items-center justify-center">
                        <span className="text-white text-xs font-bold">
                          {selectedIds.indexOf(p.id) + 1}
                        </span>
                      </div>
                    )}
                  </button>
                )
              })}
            </div>

            {/* Compare button */}
            <div className="flex justify-center">
              <button
                onClick={handleCompare}
                disabled={selectedIds.length < 2 || comparing}
                className="px-8 py-3 bg-accent hover:bg-accent-hover disabled:bg-surface disabled:text-text-muted text-white rounded-lg font-medium transition-all duration-300 hover:shadow-lg hover:shadow-accent/20 disabled:shadow-none"
              >
                {comparing ? 'Analisi in corso...' : `Confronta (${selectedIds.length}/4)`}
              </button>
            </div>

            {/* Results */}
            {compareError && (
              <div className="text-red-400 text-sm bg-red-400/10 p-3 rounded-lg text-center">
                {compareError}
              </div>
            )}
            {comparing && <LoadingSpinner />}

            {comparison && (() => {
              const hasFeatures = comparison.comparisons.some(c => c.analyzed_count > 0)
              return (
                <div className="space-y-6 animate-fade-in">
                  {/* Summary table */}
                  <div className="glow-card bg-surface rounded-xl p-5 overflow-x-auto">
                    <h3 className="text-text-primary font-display font-semibold mb-4">
                      Riepilogo
                    </h3>
                    <table className="w-full text-sm">
                      <thead>
                        <tr className="border-b border-border">
                          <th className="text-left text-text-muted py-2 px-3">Playlist</th>
                          <th className="text-center text-text-muted py-2 px-3">Brani</th>
                          <th className="text-center text-text-muted py-2 px-3">Pop. media</th>
                          {hasFeatures && (
                            <>
                              <th className="text-center text-text-muted py-2 px-3">Energia</th>
                              <th className="text-center text-text-muted py-2 px-3">Positivit&agrave;</th>
                              <th className="text-center text-text-muted py-2 px-3">Ballabilit&agrave;</th>
                            </>
                          )}
                        </tr>
                      </thead>
                      <tbody>
                        {comparison.comparisons.map((comp) => (
                          <tr key={comp.playlist_id} className="border-b border-border/50">
                            <td className="py-2 px-3 text-text-primary font-medium">
                              {playlistNames[comp.playlist_id] || comp.playlist_id}
                            </td>
                            <td className="py-2 px-3 text-center text-text-secondary">
                              {comp.track_count}
                            </td>
                            <td className="py-2 px-3 text-center text-text-secondary">
                              {comp.popularity_stats?.avg || '—'}
                            </td>
                            {hasFeatures && (
                              <>
                                <td className="py-2 px-3 text-center text-text-secondary">
                                  {Math.round((comp.averages?.energy ?? 0) * 100)}%
                                </td>
                                <td className="py-2 px-3 text-center text-text-secondary">
                                  {Math.round((comp.averages?.valence ?? 0) * 100)}%
                                </td>
                                <td className="py-2 px-3 text-center text-text-secondary">
                                  {Math.round((comp.averages?.danceability ?? 0) * 100)}%
                                </td>
                              </>
                            )}
                          </tr>
                        ))}
                      </tbody>
                    </table>
                    {!hasFeatures && (
                      <p className="text-text-muted text-xs text-center mt-3">
                        Profili audio non disponibili — le audio features di Spotify non sono al momento accessibili.
                      </p>
                    )}
                  </div>

                  {/* Top Tracks per playlist */}
                  <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
                    {comparison.comparisons.map((comp) => {
                      const tracks = comp.top_tracks || []
                      if (tracks.length === 0) return null
                      return (
                        <div key={comp.playlist_id} className="glow-card bg-surface rounded-xl p-5">
                          <div className="flex items-center gap-3 mb-4">
                            {playlistImages[comp.playlist_id] ? (
                              <img src={playlistImages[comp.playlist_id]} alt="" className="w-10 h-10 rounded-lg object-cover" />
                            ) : (
                              <div className="w-10 h-10 rounded-lg bg-surface-hover flex items-center justify-center">
                                <ListMusic size={16} className="text-text-muted" />
                              </div>
                            )}
                            <div>
                              <h4 className="text-text-primary font-display font-semibold text-sm">
                                {playlistNames[comp.playlist_id] || comp.playlist_id}
                              </h4>
                              <p className="text-text-muted text-xs">Top 10 brani per popolarit&agrave;</p>
                            </div>
                          </div>
                          <div className="space-y-1">
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
                        </div>
                      )
                    })}
                  </div>

                  {/* Genre comparison */}
                  {comparison.comparisons.some(c => Object.keys(c.genre_distribution || {}).length > 0) && (
                    <div className="glow-card bg-surface rounded-xl p-5">
                      <h3 className="text-text-primary font-display font-semibold mb-4 flex items-center gap-2">
                        <BarChart3 size={18} className="text-accent" />
                        Generi a confronto
                      </h3>
                      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
                        {comparison.comparisons.map((comp) => {
                          const genres = comp.genre_distribution || {}
                          if (Object.keys(genres).length === 0) return null
                          return (
                            <div key={comp.playlist_id}>
                              <p className="text-text-primary text-sm font-medium mb-2 truncate">
                                {playlistNames[comp.playlist_id] || comp.playlist_id}
                              </p>
                              <div className="space-y-1.5">
                                {Object.entries(genres).slice(0, 5).map(([genre, pct]) => (
                                  <div key={genre}>
                                    <div className="flex items-center justify-between mb-0.5">
                                      <span className="text-text-muted text-[10px] truncate">{genre}</span>
                                      <span className="text-text-secondary text-[10px] ml-1">{pct}%</span>
                                    </div>
                                    <div className="w-full h-1 bg-background rounded-full overflow-hidden">
                                      <div className="h-full bg-accent rounded-full" style={{ width: `${pct}%` }} />
                                    </div>
                                  </div>
                                ))}
                              </div>
                            </div>
                          )
                        })}
                      </div>
                    </div>
                  )}

                  {/* Charts only if features available */}
                  {hasFeatures && (
                    <>
                      <PlaylistComparison
                        comparisons={comparison.comparisons}
                        playlistNames={playlistNames}
                      />
                      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
                        {comparison.comparisons.map((comp, idx) => (
                          <AudioRadar
                            key={comp.playlist_id}
                            features={comp.averages}
                            title={playlistNames[comp.playlist_id] || `Playlist ${idx + 1}`}
                          />
                        ))}
                      </div>
                    </>
                  )}
                </div>
              )
            })()}
          </>
        )}
    </main>
  )
}
