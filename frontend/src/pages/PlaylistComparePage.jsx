import { useState, useEffect, useMemo, useRef } from 'react'
import { ListMusic, TrendingUp, Music, Tag, Loader2, Clock } from 'lucide-react'
import { AnimatePresence, motion } from 'framer-motion'
import {
  Bar,
  BarChart,
  CartesianGrid,
  Legend,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import PlaylistComparison from '../components/charts/PlaylistComparison'
import AudioRadar from '../components/charts/AudioRadar'
import { SkeletonGrid, SkeletonCard } from '../components/ui/Skeleton'
import { StaggerContainer, StaggerItem } from '../components/ui/StaggerContainer'
import api from '../lib/api'
import { useSpotifyData } from '../hooks/useSpotifyData'
import { usePlaylistCompare } from '../hooks/usePlaylistCompare'
import { PLAYLIST_COLORS, TOOLTIP_STYLE } from '../lib/chartTheme'
import SectionErrorBoundary from '../components/ui/SectionErrorBoundary'

/** Map backend phase strings to Italian user-facing labels */
function phaseLabel(phase, progress) {
  switch (phase) {
    case 'fetching':
    case 'fetching_tracks':
      return `Caricamento playlist ${progress.completed}/${progress.total}...`
    case 'fetching_genres':
      return 'Recupero generi...'
    case 'computing':
      return 'Calcolo risultati...'
    default:
      if (progress.total > 0 && progress.completed < progress.total) {
        return `Elaborazione ${progress.completed}/${progress.total}...`
      }
      return 'Analisi in corso...'
  }
}

export default function PlaylistComparePage() {
  const { data: playlistsData, loading: playlistsLoading } = useSpotifyData('/api/v1/playlists')

  const [selectedIds, setSelectedIds] = useState([])
  const {
    data: comparison,
    loading: comparing,
    error: compareError,
    compare,
    reset,
    progress,
    isWaiting,
    waitSeconds,
  } = usePlaylistCompare()

  // Reset stale comparison when selection changes
  const selectionKey = useMemo(() => JSON.stringify(selectedIds), [selectedIds])
  const comparisonRef = useRef(comparison)
  comparisonRef.current = comparison
  useEffect(() => {
    if (comparisonRef.current) reset()
  }, [selectionKey, reset])

  const rawPlaylists = useMemo(() => playlistsData?.playlists || [], [playlistsData])

  // Local overlay for track counts resolved by the lightweight /counts endpoint
  const [countOverrides, setCountOverrides] = useState({})

  const playlists = useMemo(
    () => rawPlaylists.map(p => ({
      ...p,
      track_count: countOverrides[p.id] ?? p.track_count,
    })),
    [rawPlaylists, countOverrides],
  )
  const ownedPlaylists = useMemo(() => playlists.filter(p => p.is_owner !== false), [playlists])
  const followedPlaylists = useMemo(() => playlists.filter(p => p.is_owner === false), [playlists])

  // Poll lightweight /counts endpoint while owned playlists still have count=0
  useEffect(() => {
    if (playlistsLoading || rawPlaylists.length === 0) return
    const needsCounts = rawPlaylists.some(
      p => (countOverrides[p.id] ?? p.track_count) === 0 && p.is_owner !== false,
    )
    if (!needsCounts) return

    let cancelled = false
    let intervalId = null

    const pollCounts = async () => {
      try {
        const res = await api.get('/api/v1/playlists/counts')
        if (cancelled || !res.data?.counts) return
        setCountOverrides(prev => ({ ...prev, ...res.data.counts }))
      } catch {
        // ignore polling errors
      }
    }

    const timeoutId = setTimeout(() => {
      if (cancelled) return
      pollCounts()
      intervalId = setInterval(pollCounts, 5000)
    }, 3000)

    return () => {
      cancelled = true
      clearTimeout(timeoutId)
      if (intervalId) clearInterval(intervalId)
    }
  }, [playlistsLoading, rawPlaylists, countOverrides])

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
  playlists.forEach((p) => { playlistNames[p.id] = p.name })

  // Determine button label based on state
  const buttonLabel = comparing
    ? (progress.percent > 0 ? `${progress.percent}%` : 'Avvio...')
    : `Confronta (${selectedIds.length}/4)`

  return (
    <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-6">
        <div>
          <h1 className="text-2xl font-display font-bold text-text-primary">
            Confronto Playlist
          </h1>
          <p className="text-text-secondary text-sm">
            Seleziona da 2 a 4 playlist per confrontare
          </p>
        </div>

        {playlistsLoading ? (
          <SkeletonGrid count={8} columns="grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4" cardHeight="h-20" />
        ) : (
          <>
            {/* Owned playlists — selectable */}
            {ownedPlaylists.length > 0 && (
              <>
                <h2 className="text-sm font-medium text-text-secondary">Le tue playlist</h2>
                <StaggerContainer className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-3">
                  {ownedPlaylists.map((p) => {
                    const isSelected = selectedIds.includes(p.id)
                    return (
                      <StaggerItem key={p.id}>
                        <button
                          onClick={() => togglePlaylist(p.id)}
                          className={`w-full flex items-center gap-3 p-3 rounded-xl text-left transition-all duration-300
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
                            <p className="text-text-muted text-xs">{p.track_count > 0 ? `${p.track_count} brani` : '...'}</p>
                          </div>
                          {isSelected && (
                            <div className="w-6 h-6 rounded-full bg-accent flex items-center justify-center">
                              <span className="text-white text-xs font-bold">
                                {selectedIds.indexOf(p.id) + 1}
                              </span>
                            </div>
                          )}
                        </button>
                      </StaggerItem>
                    )
                  })}
                </StaggerContainer>
              </>
            )}

            {/* Followed playlists — visible but not selectable */}
            {followedPlaylists.length > 0 && (
              <>
                <h2 className="text-sm font-medium text-text-secondary">Playlist seguite</h2>
                <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-3">
                  {followedPlaylists.map((p) => (
                    <div
                      key={p.id}
                      className="w-full flex items-center gap-3 p-3 rounded-xl text-left opacity-50 cursor-not-allowed glow-card bg-surface"
                      title="Non disponibile per il confronto in modalità sviluppo"
                    >
                      {p.image ? (
                        <img src={p.image} alt={p.name} className="w-12 h-12 rounded-lg object-cover grayscale" />
                      ) : (
                        <div className="w-12 h-12 rounded-lg bg-surface-hover flex items-center justify-center">
                          <ListMusic size={20} className="text-text-muted" />
                        </div>
                      )}
                      <div className="flex-1 min-w-0">
                        <p className="text-text-primary text-sm font-medium truncate">{p.name}</p>
                        <p className="text-text-muted text-xs">{p.track_count > 0 ? `${p.track_count} brani` : '\u2014'}</p>
                      </div>
                    </div>
                  ))}
                </div>
              </>
            )}

            {/* Compare button */}
            <div className="flex justify-center">
              <button
                onClick={handleCompare}
                disabled={selectedIds.length < 2 || comparing}
                className="px-8 py-3 bg-accent hover:bg-accent-hover disabled:bg-surface disabled:text-text-muted text-white rounded-lg font-medium transition-all duration-300 hover:shadow-lg hover:shadow-accent/20 disabled:shadow-none flex items-center gap-2"
              >
                {comparing && <Loader2 size={16} className="animate-spin" />}
                {buttonLabel}
              </button>
            </div>

            {/* Progress indicator */}
            <AnimatePresence>
              {comparing && (
                <motion.div
                  initial={{ opacity: 0, y: -8 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, y: -8 }}
                  transition={{ duration: 0.3 }}
                  className="space-y-3"
                >
                  {/* Phase label */}
                  <div className="flex items-center justify-center gap-2 text-sm text-text-secondary">
                    {isWaiting ? (
                      <>
                        <Clock size={14} className="text-amber-400" />
                        <span className="text-amber-400">
                          In attesa rinnovo budget API ({waitSeconds}s)...
                        </span>
                      </>
                    ) : (
                      <>
                        <Loader2 size={14} className="animate-spin text-accent" />
                        <span>{phaseLabel(progress.phase, progress)}</span>
                      </>
                    )}
                  </div>

                  {/* Progress bar */}
                  {progress.total > 0 && (
                    <div className="max-w-md mx-auto">
                      <div className="h-1.5 bg-surface-hover rounded-full overflow-hidden">
                        <motion.div
                          className="h-full rounded-full"
                          style={{ backgroundColor: isWaiting ? '#f59e0b' : '#6366f1' }}
                          initial={{ width: 0 }}
                          animate={{ width: `${progress.percent}%` }}
                          transition={{ duration: 0.4, ease: 'easeOut' }}
                        />
                      </div>
                    </div>
                  )}

                  {/* Skeleton placeholders for results */}
                  <div className="space-y-4">
                    <SkeletonCard height="h-48" />
                    <SkeletonCard height="h-72" />
                  </div>
                </motion.div>
              )}
            </AnimatePresence>

            {/* Results */}
            {compareError && (
              <div className="text-red-400 text-sm bg-red-400/10 p-3 rounded-lg text-center">
                {compareError}
              </div>
            )}

            {comparison && (() => {
              const comps = comparison.comparisons
              if (!comps?.length) return null
              const hasFeatures = comps.some(c => c.analyzed_count > 0)

              // Popularity chart data
              const popData = comps.map((c, idx) => ({
                name: c.playlist_name || playlistNames[c.playlist_id] || `Playlist ${idx + 1}`,
                'Pop. media': c.popularity_stats?.avg ?? 0,
                'Pop. min': c.popularity_stats?.min ?? 0,
                'Pop. max': c.popularity_stats?.max ?? 0,
              }))

              // Genre chart data — collect all unique genres across playlists
              const allGenres = new Set()
              comps.forEach(c => {
                Object.keys(c.genre_distribution || {}).forEach(g => allGenres.add(g))
              })
              const topGenres = [...allGenres].slice(0, 8)
              const genreData = topGenres.map(genre => {
                const row = { genre }
                comps.forEach((c, idx) => {
                  const name = c.playlist_name || playlistNames[c.playlist_id] || `Playlist ${idx + 1}`
                  row[name] = c.genre_distribution?.[genre] ?? 0
                })
                return row
              })
              const genreBarNames = comps.map(
                (c, idx) => c.playlist_name || playlistNames[c.playlist_id] || `Playlist ${idx + 1}`
              )

              return (
                <SectionErrorBoundary sectionName="ComparisonResults">
                <motion.div
                  initial={{ opacity: 0, y: 12 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ duration: 0.4 }}
                  className="space-y-6"
                >
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
                          <th className="text-center text-text-muted py-2 px-3">Genere principale</th>
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
                        {comps.map((comp, idx) => {
                          const genres = Object.entries(comp.genre_distribution || {})
                          const topGenre = genres.length > 0
                            ? genres.sort((a, b) => b[1] - a[1])[0][0]
                            : '\u2014'
                          return (
                            <tr key={comp.playlist_id} className="border-b border-border/50">
                              <td className="py-2 px-3 text-text-primary font-medium">
                                <div className="flex items-center gap-2">
                                  <div
                                    className="w-2.5 h-2.5 rounded-full flex-shrink-0"
                                    style={{ backgroundColor: PLAYLIST_COLORS[idx % PLAYLIST_COLORS.length] }}
                                  />
                                  {comp.playlist_name || playlistNames[comp.playlist_id] || comp.playlist_id}
                                </div>
                              </td>
                              <td className="py-2 px-3 text-center text-text-secondary">
                                {comp.track_count}
                              </td>
                              <td className="py-2 px-3 text-center text-text-secondary">
                                {comp.popularity_stats?.avg ?? 0}
                              </td>
                              <td className="py-2 px-3 text-center text-text-secondary capitalize">
                                {topGenre}
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
                          )
                        })}
                      </tbody>
                    </table>
                  </div>

                  {/* Popularity comparison bar chart */}
                  <div className="glow-card bg-surface rounded-xl p-5">
                    <h3 className="text-text-primary font-display font-semibold mb-4 flex items-center gap-2">
                      <TrendingUp size={18} className="text-accent" />
                      Confronto Popolarit&agrave;
                    </h3>
                    <ResponsiveContainer width="100%" height={300}>
                      <BarChart data={popData} margin={{ top: 5, right: 20, left: 0, bottom: 5 }}>
                        <CartesianGrid strokeDasharray="3 3" stroke="#282828" />
                        <XAxis
                          dataKey="name"
                          tick={{ fill: '#b3b3b3', fontSize: 11 }}
                          axisLine={{ stroke: '#282828' }}
                        />
                        <YAxis
                          domain={[0, 100]}
                          tick={{ fill: '#b3b3b3', fontSize: 12 }}
                          axisLine={{ stroke: '#282828' }}
                        />
                        <Tooltip {...TOOLTIP_STYLE} />
                        <Bar dataKey="Pop. media" fill="#6366f1" radius={[4, 4, 0, 0]} animationDuration={1200} />
                        <Bar dataKey="Pop. min" fill="#4b5563" radius={[4, 4, 0, 0]} animationDuration={1200} animationBegin={200} />
                        <Bar dataKey="Pop. max" fill="#10b981" radius={[4, 4, 0, 0]} animationDuration={1200} animationBegin={400} />
                        <Legend wrapperStyle={{ color: '#b3b3b3', fontSize: 12 }} />
                      </BarChart>
                    </ResponsiveContainer>
                  </div>

                  {/* Genre distribution comparison */}
                  {genreData.length > 0 && (
                    <div className="glow-card bg-surface rounded-xl p-5">
                      <h3 className="text-text-primary font-display font-semibold mb-4 flex items-center gap-2">
                        <Tag size={18} className="text-accent" />
                        Distribuzione Generi
                      </h3>
                      <ResponsiveContainer width="100%" height={400}>
                        <BarChart data={genreData} layout="vertical" margin={{ top: 5, right: 20, left: 10, bottom: 5 }}>
                          <CartesianGrid strokeDasharray="3 3" stroke="#282828" />
                          <XAxis
                            type="number"
                            domain={[0, 'auto']}
                            tick={{ fill: '#b3b3b3', fontSize: 12 }}
                            axisLine={{ stroke: '#282828' }}
                            tickFormatter={(v) => `${v}%`}
                          />
                          <YAxis
                            type="category"
                            dataKey="genre"
                            tick={{ fill: '#b3b3b3', fontSize: 11 }}
                            axisLine={{ stroke: '#282828' }}
                            width={75}
                          />
                          <Tooltip
                            {...TOOLTIP_STYLE}
                            formatter={(val) => [`${val}%`, '']}
                          />
                          <Legend wrapperStyle={{ color: '#b3b3b3', fontSize: 12 }} />
                          {genreBarNames.map((name, idx) => (
                            <Bar
                              key={name}
                              dataKey={name}
                              fill={PLAYLIST_COLORS[idx % PLAYLIST_COLORS.length]}
                              radius={[0, 4, 4, 0]}
                              animationDuration={1200}
                              animationBegin={idx * 200}
                            />
                          ))}
                        </BarChart>
                      </ResponsiveContainer>
                    </div>
                  )}

                  {/* Top tracks per playlist */}
                  <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
                    {comps.map((comp, idx) => {
                      const name = comp.playlist_name || playlistNames[comp.playlist_id] || `Playlist ${idx + 1}`
                      return (
                        <div key={comp.playlist_id} className="glow-card bg-surface rounded-xl p-5">
                          <h3 className="text-text-primary font-display font-semibold mb-3 flex items-center gap-2">
                            <Music size={16} className="text-accent" />
                            <span className="truncate">{name}</span>
                            <span className="text-text-muted text-xs font-normal ml-auto">Top 5</span>
                          </h3>
                          <div className="space-y-2">
                            {(comp.top_tracks || []).map((track, tIdx) => (
                              <div key={tIdx} className="flex items-center gap-3 py-1.5">
                                <span className="text-text-muted text-xs w-5 text-right">{tIdx + 1}</span>
                                <div className="flex-1 min-w-0">
                                  <p className="text-text-primary text-sm truncate">{track.name}</p>
                                  <p className="text-text-muted text-xs truncate">{track.artist}</p>
                                </div>
                                <span className="text-xs px-2 py-0.5 rounded-full bg-accent/10 text-accent font-medium">
                                  Pop. {track.popularity}
                                </span>
                              </div>
                            ))}
                          </div>
                        </div>
                      )
                    })}
                  </div>

                  {/* Audio features charts — only when available */}
                  {hasFeatures && (
                    <>
                      <PlaylistComparison
                        comparisons={comps}
                        playlistNames={playlistNames}
                      />
                      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
                        {comps.map((comp, idx) => (
                          <AudioRadar
                            key={comp.playlist_id}
                            features={comp.averages}
                            title={comp.playlist_name || playlistNames[comp.playlist_id] || `Playlist ${idx + 1}`}
                          />
                        ))}
                      </div>
                    </>
                  )}
                </motion.div>
                </SectionErrorBoundary>
              )
            })()}
          </>
        )}
    </main>
  )
}
