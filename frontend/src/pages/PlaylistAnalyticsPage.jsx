import { useEffect, useRef, useCallback } from 'react'
import { AnimatePresence, motion } from 'framer-motion'
import KPICard from '../components/cards/KPICard'
import PlaylistStatCard from '../components/cards/PlaylistStatCard'
import OverlapHeatmap from '../components/charts/OverlapHeatmap'
import { SkeletonKPICard, SkeletonCard } from '../components/ui/Skeleton'
import { StaggerContainer, StaggerItem } from '../components/ui/StaggerContainer'
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts'
import { TOOLTIP_STYLE } from '../lib/chartTheme'
import { ListMusic, Globe, Lock, Users, RefreshCw, Loader2, Clock, AlertTriangle } from 'lucide-react'
import SectionErrorBoundary from '../components/ui/SectionErrorBoundary'
import { usePlaylistTask } from '../hooks/usePlaylistTask'

/** Map backend phase strings to Italian user-facing labels */
function phaseLabel(phase, progress) {
  switch (phase) {
    case 'listing':
      return 'Recupero elenco playlist...'
    case 'analyzing':
    case 'fetching_tracks':
      return `Analisi playlist ${progress.completed}/${progress.total}...`
    case 'fetching_genres':
      return 'Recupero generi...'
    case 'computing':
      return 'Calcolo statistiche finali...'
    default:
      if (progress.total > 0 && progress.completed < progress.total) {
        return `Analisi playlist ${progress.completed}/${progress.total}...`
      }
      return 'Caricamento...'
  }
}

export default function PlaylistAnalyticsPage() {
  const {
    data,
    progress,
    isLoading: loading,
    isWaiting,
    waitSeconds,
    error,
    start,
    reset,
  } = usePlaylistTask({
    postUrl: '/api/v1/playlist-analytics',
    pollUrl: (taskId) => `/api/v1/playlist-analytics/${taskId}`,
  })

  const startedRef = useRef(false)

  // Auto-start on mount
  useEffect(() => {
    if (!startedRef.current) {
      startedRef.current = true
      start({})
    }
  }, [start])

  const handleRefresh = useCallback(() => {
    reset()
    startedRef.current = false
    // Small delay to allow state to clear before restarting
    setTimeout(() => {
      startedRef.current = true
      start({})
    }, 50)
  }, [reset, start])

  const summary = data?.summary || {}
  const sizeDistribution = data?.size_distribution || []
  const playlists = data?.playlists || []
  const overlapMatrix = data?.overlap_matrix || {}

  // Determine which sections can be shown based on available data
  const hasSummary = summary.total_playlists != null
  const hasPlaylists = playlists.length > 0
  const hasOverlap = (overlapMatrix.labels || []).length > 0

  return (
    <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-6">
        <div className="flex items-center justify-between gap-3">
          <div>
            <h1 className="text-2xl font-display font-bold text-text-primary">Analisi Playlist</h1>
            <p className="text-text-secondary text-sm mt-1">Statistiche approfondite sulle tue playlist</p>
          </div>
          <button
            onClick={handleRefresh}
            disabled={loading}
            className="p-2 min-h-[36px] min-w-[36px] rounded-lg text-text-muted hover:text-text-primary hover:bg-surface-hover transition-all duration-300 flex-shrink-0 disabled:opacity-50"
            title="Aggiorna"
          >
            <RefreshCw size={18} className={loading ? 'animate-spin' : ''} />
          </button>
        </div>

        {error && data && (
          <div className="bg-yellow-500/10 border border-yellow-500/20 text-yellow-300 text-sm rounded-lg p-3 flex items-center gap-2">
            <AlertTriangle className="w-4 h-4 shrink-0" />
            <span>Analisi parziale — {error}. I dati mostrati potrebbero essere incompleti.</span>
          </div>
        )}

        {error && !data && (
          <div className="bg-red-500/10 border border-red-500/20 rounded-xl p-4 text-red-400 text-sm">{error}</div>
        )}

        {/* Progress indicator while loading */}
        <AnimatePresence>
          {loading && (
            <motion.div
              initial={{ opacity: 0, y: -8 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -8 }}
              transition={{ duration: 0.3 }}
              className="space-y-2"
            >
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
            </motion.div>
          )}
        </AnimatePresence>

        {/* Frozen progress bar when error occurred with partial data */}
        {!loading && error && data && progress.total > 0 && (
          <div className="max-w-md mx-auto">
            <div className="h-1.5 bg-surface-hover rounded-full overflow-hidden">
              <div
                className="h-full rounded-full transition-all duration-300"
                style={{ backgroundColor: '#f59e0b', width: `${progress.percent}%` }}
              />
            </div>
            <p className="text-text-muted text-xs text-center mt-1">
              {progress.completed}/{progress.total} playlist analizzate
            </p>
          </div>
        )}

        {/* KPI Cards — show as soon as summary data is available, or skeletons while loading */}
        {loading && !hasSummary ? (
          <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-4">
            {Array.from({ length: 4 }).map((_, i) => (
              <SkeletonKPICard key={i} />
            ))}
          </div>
        ) : hasSummary ? (
          <SectionErrorBoundary sectionName="KPICards">
            <StaggerContainer className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-4">
              <StaggerItem>
                <KPICard title="Totale Playlist" value={summary.total_playlists || 0} icon={ListMusic} delay={0} tooltip="Numero totale di playlist nel tuo account Spotify" />
              </StaggerItem>
              <StaggerItem>
                <KPICard title="Pubbliche" value={summary.public_count || 0} icon={Globe} delay={100} tooltip="Playlist visibili a tutti gli utenti Spotify" />
              </StaggerItem>
              <StaggerItem>
                <KPICard title="Private" value={summary.private_count || 0} icon={Lock} delay={200} tooltip="Playlist visibili solo a te" />
              </StaggerItem>
              <StaggerItem>
                <KPICard title="Collaborative" value={summary.collaborative_count || 0} icon={Users} delay={300} tooltip="Playlist a cui altri utenti possono aggiungere brani" />
              </StaggerItem>
            </StaggerContainer>
          </SectionErrorBoundary>
        ) : null}

        {/* Size Distribution — show as soon as data arrives */}
        {loading && !hasSummary ? (
          <SkeletonCard height="h-72" />
        ) : sizeDistribution.length > 0 ? (
          <SectionErrorBoundary sectionName="SizeDistribution">
            <motion.div
              initial={{ opacity: 0, y: 12 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.4 }}
              className="glow-card bg-surface rounded-xl p-5"
            >
              <h3 className="text-text-primary font-display font-semibold mb-4">Distribuzione Dimensioni</h3>
              <ResponsiveContainer width="100%" height={250}>
                <BarChart data={sizeDistribution} margin={{ top: 5, right: 20, left: 0, bottom: 5 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#282828" />
                  <XAxis dataKey="range" tick={{ fill: '#b3b3b3', fontSize: 12 }} />
                  <YAxis tick={{ fill: '#b3b3b3', fontSize: 12 }} />
                  <Tooltip {...TOOLTIP_STYLE} formatter={(value) => [`${value} playlist`, 'Conteggio']} />
                  <Bar dataKey="count" fill="#6366f1" radius={[4, 4, 0, 0]} animationDuration={1500} />
                </BarChart>
              </ResponsiveContainer>
              <p className="text-text-muted text-xs text-center mt-2">
                Dimensione media: {summary.avg_size || 0} tracce &middot; Totale: {summary.total_tracks || 0} tracce
              </p>
            </motion.div>
          </SectionErrorBoundary>
        ) : null}

        {/* Playlist Cards Grid — show as soon as playlists arrive */}
        {loading && !hasPlaylists ? (
          <SkeletonCard height="h-48" />
        ) : hasPlaylists ? (
          <SectionErrorBoundary sectionName="PlaylistCards">
            <motion.div
              initial={{ opacity: 0, y: 12 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.4, delay: 0.1 }}
            >
              <h3 className="text-text-primary font-display font-semibold mb-4">Dettaglio Playlist</h3>
              <StaggerContainer className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
                {playlists.map((playlist, i) => (
                  <StaggerItem key={playlist.id}>
                    <PlaylistStatCard playlist={playlist} index={i} />
                  </StaggerItem>
                ))}
              </StaggerContainer>
            </motion.div>
          </SectionErrorBoundary>
        ) : null}

        {/* Overlap Heatmap — show as soon as overlap data arrives */}
        {loading && !hasOverlap ? (
          <SkeletonCard height="h-64" />
        ) : hasOverlap ? (
          <SectionErrorBoundary sectionName="OverlapHeatmap">
            <motion.div
              initial={{ opacity: 0, y: 12 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.4, delay: 0.2 }}
            >
              <OverlapHeatmap
                labels={overlapMatrix.labels || []}
                matrix={overlapMatrix.matrix || []}
              />
            </motion.div>
          </SectionErrorBoundary>
        ) : null}
      </main>
  )
}
