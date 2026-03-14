import { useSpotifyData } from '../hooks/useSpotifyData'
import KPICard from '../components/cards/KPICard'
import ArtistNetwork from '../components/charts/ArtistNetwork'
import { SkeletonKPICard, SkeletonCard } from '../components/ui/Skeleton'
import { StaggerContainer, StaggerItem } from '../components/ui/StaggerContainer'
import { Users, GitBranch, Waypoints, BarChart3, RefreshCw, Music, AlertTriangle } from 'lucide-react'

export default function ArtistNetworkPage() {
  const { data, loading, error, refetch } = useSpotifyData('/api/artist-network')

  const metrics = data?.metrics || {}
  const nodes = data?.nodes || []
  const edges = data?.edges || []
  const clusters = data?.clusters || []
  const clusterNames = data?.cluster_names || {}
  const bridges = data?.bridges || []
  const topGenres = data?.top_genres || []
  const clusterRankings = data?.cluster_rankings || {}
  const dataQuality = data?.data_quality || {}

  return (
    <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-6">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-display font-bold text-text-primary">Ecosistema Artisti</h1>
            <p className="text-text-secondary text-sm mt-1">La rete di connessioni tra i tuoi artisti preferiti</p>
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
            <SkeletonCard height="h-96" />
          </div>
        ) : (
          <>
            {/* KPI Cards */}
            <StaggerContainer className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-4">
              <StaggerItem>
                <KPICard title="Artisti nel Grafo" value={metrics.total_nodes || 0} icon={Users} delay={0} tooltip="I tuoi artisti più ascoltati da 3 periodi, collegati per generi musicali condivisi" />
              </StaggerItem>
              <StaggerItem>
                <KPICard title="Connessioni" value={metrics.total_edges || 0} icon={GitBranch} delay={100} tooltip="Ogni connessione indica generi musicali condivisi. Più generi in comune, connessione più forte" />
              </StaggerItem>
              <StaggerItem>
                <KPICard title="Cerchie" value={metrics.cluster_count || 0} icon={Waypoints} delay={200} tooltip="Gruppi di artisti che formano una rete connessa. Il nome della cerchia è il genere dominante tra gli artisti del gruppo" />
              </StaggerItem>
              <StaggerItem>
                <KPICard title="Densità Rete" value={Math.round((metrics.density || 0) * 100)} suffix="%" icon={BarChart3} delay={300} tooltip="Quanto è interconnesso il tuo ecosistema musicale. 100% = tutti gli artisti condividono generi" />
              </StaggerItem>
            </StaggerContainer>

            {data?.data_quality?.warning && (
              <div className="bg-amber-500/10 border border-amber-500/20 rounded-xl px-4 py-3 flex items-center gap-2">
                <AlertTriangle size={16} className="text-amber-400 flex-shrink-0" />
                <p className="text-amber-400 text-sm">{data.data_quality.warning}</p>
              </div>
            )}

            {/* Network Graph */}
            <ArtistNetwork nodes={nodes} edges={edges} clusters={clusters} clusterNames={clusterNames} loading={loading} />

            {/* Genre Cloud */}
            {topGenres.length > 0 && (
              <div className="glow-card bg-surface rounded-xl p-5">
                <h3 className="text-text-primary font-display font-semibold mb-4 flex items-center gap-2">
                  <Music size={18} className="text-accent" />
                  Generi dominanti nel tuo ecosistema
                </h3>
                <StaggerContainer className="flex flex-wrap gap-2">
                  {topGenres.map((g, i) => {
                    const size = i < 3 ? 'text-sm px-3 py-1.5' : 'text-xs px-2 py-1'
                    const opacity = Math.max(0.4, 1 - (i * 0.08))
                    return (
                      <StaggerItem key={g.genre}>
                        <span
                          className={`${size} rounded-full bg-accent/10 text-accent font-medium transition-all hover:bg-accent/20 inline-block`}
                          style={{ opacity }}
                        >
                          {g.genre}
                          <span className="text-text-muted ml-1 text-[10px]">({g.count})</span>
                        </span>
                      </StaggerItem>
                    )
                  })}
                </StaggerContainer>
              </div>
            )}

            {/* Bridge Artists */}
            {bridges.length > 0 && (
              <div className="glow-card bg-surface rounded-xl p-5">
                <h3 className="text-text-primary font-display font-semibold mb-4 flex items-center gap-2">
                  <Waypoints size={18} className="text-accent" />
                  Artisti Ponte
                </h3>
                <p className="text-text-secondary text-sm mb-4">
                  Artisti che collegano cerchie di gusto diverse nel tuo ecosistema
                </p>
                <StaggerContainer className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-3">
                  {bridges.map((bridge) => (
                    <StaggerItem key={bridge.id}>
                      <div className="flex items-start gap-3 p-3 rounded-lg bg-surface-hover">
                        {bridge.image ? (
                          <img src={bridge.image} alt={bridge.name} className="w-12 h-12 rounded-full object-cover flex-shrink-0" />
                        ) : (
                          <div className="w-12 h-12 rounded-full bg-background flex items-center justify-center flex-shrink-0">
                            <Users size={18} className="text-text-muted" />
                          </div>
                        )}
                        <div className="min-w-0">
                          <p className="text-text-primary text-sm font-medium truncate">{bridge.name}</p>
                          <p className="text-accent text-xs">{bridge.bridge_score} conn. tra cerchie</p>
                          {bridge.genres && bridge.genres.length > 0 && (
                            <p className="text-text-muted text-[10px] truncate mt-0.5">{bridge.genres.join(', ')}</p>
                          )}
                          {bridge.popularity > 0 && (
                            <p className="text-text-muted text-[10px]">Pop. {bridge.popularity}</p>
                          )}
                        </div>
                      </div>
                    </StaggerItem>
                  ))}
                </StaggerContainer>
              </div>
            )}

            {/* Top per Cerchia */}
            {Object.keys(clusterRankings).length > 0 && (
              <div className="glow-card bg-surface rounded-xl p-5">
                <h3 className="text-text-primary font-display font-semibold mb-4 flex items-center gap-2">
                  <Users size={18} className="text-accent" />
                  Top per Cerchia
                </h3>
                <p className="text-text-secondary text-sm mb-4">
                  L'artista più influente in ciascuna cerchia del tuo ecosistema
                </p>
                <StaggerContainer className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-3">
                  {Object.entries(clusterRankings).map(([clusterId, artists]) => {
                    const topArtist = artists[0]
                    if (!topArtist) return null
                    const cName = clusterNames[clusterId] || `Cerchia ${Number(clusterId) + 1}`
                    return (
                      <StaggerItem key={clusterId}>
                        <div className="flex items-start gap-3 p-3 rounded-lg bg-surface-hover">
                          {topArtist.image ? (
                            <img src={topArtist.image} alt={topArtist.name} className="w-12 h-12 rounded-full object-cover flex-shrink-0" />
                          ) : (
                            <div className="w-12 h-12 rounded-full bg-background flex items-center justify-center flex-shrink-0">
                              <Users size={18} className="text-text-muted" />
                            </div>
                          )}
                          <div className="min-w-0">
                            <p className="text-text-primary text-sm font-medium truncate">{topArtist.name}</p>
                            <p className="text-accent text-xs">{cName}</p>
                            <p className="text-text-muted text-[10px]">Score: {Math.round(topArtist.score * 100)}%</p>
                          </div>
                        </div>
                      </StaggerItem>
                    )
                  })}
                </StaggerContainer>
              </div>
            )}
          </>
        )}
      </main>
  )
}
