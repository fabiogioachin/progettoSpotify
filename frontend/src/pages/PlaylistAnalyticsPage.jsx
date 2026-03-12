import { useSpotifyData } from '../hooks/useSpotifyData'
import KPICard from '../components/cards/KPICard'
import PlaylistStatCard from '../components/cards/PlaylistStatCard'
import OverlapHeatmap from '../components/charts/OverlapHeatmap'
import { SkeletonKPICard, SkeletonCard } from '../components/ui/Skeleton'
import { StaggerContainer, StaggerItem } from '../components/ui/StaggerContainer'
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts'
import { TOOLTIP_STYLE } from '../lib/chartTheme'
import { ListMusic, Globe, Lock, Users, RefreshCw } from 'lucide-react'

export default function PlaylistAnalyticsPage() {
  const { data, loading, error, refetch } = useSpotifyData('/api/playlist-analytics')

  const summary = data?.summary || {}
  const sizeDistribution = data?.size_distribution || []
  const playlists = data?.playlists || []
  const overlapMatrix = data?.overlap_matrix || {}

  return (
    <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-6">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-display font-bold text-text-primary">Analisi Playlist</h1>
            <p className="text-text-secondary text-sm mt-1">Statistiche approfondite sulle tue playlist</p>
          </div>
          <button onClick={() => refetch()} className="p-2 rounded-lg text-text-muted hover:text-text-primary hover:bg-surface-hover transition-all duration-300" title="Aggiorna">
            <RefreshCw size={18} />
          </button>
        </div>

        {error && (
          <div className="bg-red-500/10 border border-red-500/20 rounded-xl p-4 text-red-400 text-sm">{error}</div>
        )}

        {loading ? (
          <div className="space-y-6">
            <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-4">
              {Array.from({ length: 4 }).map((_, i) => (
                <SkeletonKPICard key={i} />
              ))}
            </div>
            <SkeletonCard height="h-72" />
          </div>
        ) : (
          <>
            {/* KPI Cards */}
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

            {/* Size Distribution */}
            <div className="glow-card bg-surface rounded-xl p-5">
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
                Dimensione media: {summary.avg_size || 0} tracce · Totale: {summary.total_tracks || 0} tracce
              </p>
            </div>

            {/* Playlist Cards Grid */}
            {playlists.length > 0 && (
              <div>
                <h3 className="text-text-primary font-display font-semibold mb-4">Dettaglio Playlist</h3>
                <StaggerContainer className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
                  {playlists.map((playlist, i) => (
                    <StaggerItem key={playlist.id}>
                      <PlaylistStatCard playlist={playlist} index={i} />
                    </StaggerItem>
                  ))}
                </StaggerContainer>
              </div>
            )}

            {/* Overlap Heatmap */}
            <OverlapHeatmap
              labels={overlapMatrix.labels || []}
              matrix={overlapMatrix.matrix || []}
            />
          </>
        )}
      </main>
  )
}
