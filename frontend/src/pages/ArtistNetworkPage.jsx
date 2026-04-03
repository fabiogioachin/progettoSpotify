import { useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { useSpotifyData } from '../hooks/useSpotifyData'
import KPICard from '../components/cards/KPICard'
import ArtistNetwork from '../components/charts/ArtistNetwork'
import { SkeletonKPICard, SkeletonCard } from '../components/ui/Skeleton'
import { StaggerContainer, StaggerItem } from '../components/ui/StaggerContainer'
import { Users, GitBranch, Waypoints, BarChart3, RefreshCw, Music, AlertTriangle, ChevronDown, ChevronUp } from 'lucide-react'
import SectionErrorBoundary from '../components/ui/SectionErrorBoundary'

export default function ArtistNetworkPage() {
  const { data, loading, error, refetch } = useSpotifyData('/api/v1/artist-network')

  const metrics = data?.metrics || {}
  const nodes = data?.nodes || []
  const edges = data?.edges || []
  const clusters = data?.clusters || []
  const clusterNames = data?.cluster_names || {}
  const bridges = data?.bridges || []
  const topGenres = data?.top_genres || []
  const clusterRankings = data?.cluster_rankings || {}
  const genreNodes = data?.genre_nodes || []
  const genreEdges = data?.genre_edges || []


  return (
    <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-6">
        <div className="flex items-center justify-between gap-3">
          <div>
            <h1 className="text-2xl font-display font-bold text-text-primary">Ecosistema Artisti</h1>
            <p className="text-text-secondary text-sm mt-1">La rete di connessioni tra i tuoi artisti preferiti</p>
          </div>
          <button onClick={() => refetch()} className="p-2 min-h-[36px] min-w-[36px] rounded-lg text-text-muted hover:text-text-primary hover:bg-surface-hover transition-all duration-300 flex-shrink-0" title="Aggiorna">
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
            <SectionErrorBoundary sectionName="KPICards">
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
            </SectionErrorBoundary>

            {data?.data_quality?.warning && (
              <div className="bg-amber-500/10 border border-amber-500/20 rounded-xl px-4 py-3 flex items-center gap-2">
                <AlertTriangle size={16} className="text-amber-400 flex-shrink-0" />
                <p className="text-amber-400 text-sm">{data.data_quality.warning}</p>
              </div>
            )}

            {/* Network Graph */}
            <SectionErrorBoundary sectionName="ArtistNetwork">
              <ArtistNetwork
                nodes={nodes}
                edges={edges}
                clusters={clusters}
                clusterNames={clusterNames}
                loading={loading}
                genreNodes={genreNodes}
                genreEdges={genreEdges}
              />
              <p className="text-text-muted text-xs text-center mt-2">Usa la rotella del mouse per esplorare le connessioni</p>
            </SectionErrorBoundary>

            {/* Genre Cloud */}
            {topGenres.length > 0 && (
              <SectionErrorBoundary sectionName="GenreCloud">
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
              </SectionErrorBoundary>
            )}

            {/* Bridge Artists */}
            {bridges.length > 0 && (
              <SectionErrorBoundary sectionName="BridgeArtists">
              <div className="glow-card bg-surface rounded-xl p-5">
                <h3 className="text-text-primary font-display font-semibold mb-4 flex items-center gap-2">
                  <Waypoints size={18} className="text-accent" />
                  Artisti Ponte
                </h3>
                <p className="text-text-secondary text-sm mb-4">
                  Artisti che collegano cerchie di gusto diverse nel tuo ecosistema
                </p>
                <StaggerContainer className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-3">
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
              </SectionErrorBoundary>
            )}

            {/* Le tue Cerchie */}
            {Object.keys(clusterRankings).length > 0 && (
              <SectionErrorBoundary sectionName="CerchieSection">
                <CerchieSection clusterRankings={clusterRankings} clusterNames={clusterNames} />
              </SectionErrorBoundary>
            )}
          </>
        )}
      </main>
  )
}

const CLUSTER_COLORS = [
  '#6366f1', '#1DB954', '#f59e0b', '#ec4899', '#06b6d4',
  '#8b5cf6', '#ef4444', '#10b981', '#f97316', '#14b8a6',
]

function CerchieSection({ clusterRankings, clusterNames }) {
  const sortedEntries = Object.entries(clusterRankings)
    .filter(([, artists]) => artists.length > 0)
    .sort((a, b) => b[1].length - a[1].length)

  const [expanded, setExpanded] = useState(() => {
    const initial = {}
    sortedEntries.slice(0, 3).forEach(([id]) => { initial[id] = true })
    return initial
  })

  const toggle = (id) => {
    setExpanded(prev => ({ ...prev, [id]: !prev[id] }))
  }

  return (
    <div className="space-y-4">
      <div>
        <h3 className="text-text-primary font-display font-semibold text-lg flex items-center gap-2">
          <Users size={20} className="text-accent" />
          Le tue Cerchie
        </h3>
        <p className="text-text-secondary text-sm mt-1">
          Tutti gli artisti raggruppati per cerchia musicale
        </p>
      </div>
      <StaggerContainer className="space-y-3">
        {sortedEntries.map(([clusterId, artists]) => {
          const cName = clusterNames[clusterId] || `Cerchia ${Number(clusterId) + 1}`
          const color = CLUSTER_COLORS[Number(clusterId) % CLUSTER_COLORS.length]
          const isOpen = !!expanded[clusterId]

          return (
            <StaggerItem key={clusterId}>
              <div className="glow-card bg-surface rounded-xl overflow-hidden">
                <button
                  type="button"
                  onClick={() => toggle(clusterId)}
                  className="w-full flex items-center justify-between px-5 py-4 hover:bg-surface-hover transition-colors duration-200"
                  aria-expanded={isOpen}
                >
                  <div className="flex items-center gap-3">
                    <div className="w-3 h-3 rounded-full flex-shrink-0" style={{ backgroundColor: color }} />
                    <span className="text-text-primary font-display font-semibold text-sm">{cName}</span>
                    <span className="text-text-muted text-xs">({artists.length} artisti)</span>
                  </div>
                  {isOpen ? (
                    <ChevronUp size={16} className="text-text-muted" />
                  ) : (
                    <ChevronDown size={16} className="text-text-muted" />
                  )}
                </button>
                <AnimatePresence initial={false}>
                  {isOpen && (
                    <motion.div
                      initial={{ height: 0, opacity: 0 }}
                      animate={{ height: 'auto', opacity: 1 }}
                      exit={{ height: 0, opacity: 0 }}
                      transition={{ duration: 0.25, ease: 'easeInOut' }}
                      className="overflow-hidden"
                    >
                      <div className="px-5 pb-4 space-y-2">
                        {artists.map((artist) => (
                          <div
                            key={artist.name}
                            className="flex items-center gap-3 p-2 rounded-lg hover:bg-surface-hover transition-colors duration-200"
                          >
                            {artist.image ? (
                              <img
                                src={artist.image}
                                alt={artist.name}
                                className="w-10 h-10 rounded-full object-cover flex-shrink-0"
                              />
                            ) : (
                              <div className="w-10 h-10 rounded-full bg-surface-hover flex items-center justify-center flex-shrink-0">
                                <Users size={14} className="text-text-muted" />
                              </div>
                            )}
                            <div className="flex-1 min-w-0">
                              <div className="flex items-center justify-between gap-2">
                                <p className="text-text-primary text-sm font-medium truncate">{artist.name}</p>
                                <span className="text-text-muted text-xs flex-shrink-0">
                                  {Math.round(artist.score * 100)}%
                                </span>
                              </div>
                              {artist.genres && artist.genres.length > 0 && (
                                <p className="text-text-muted text-[10px] truncate">{artist.genres.join(', ')}</p>
                              )}
                              <div className="w-full h-1 bg-background rounded-full overflow-hidden mt-1">
                                <div
                                  className="h-full rounded-full transition-all duration-500"
                                  style={{
                                    width: `${Math.round(artist.score * 100)}%`,
                                    backgroundColor: color,
                                  }}
                                />
                              </div>
                            </div>
                          </div>
                        ))}
                      </div>
                    </motion.div>
                  )}
                </AnimatePresence>
              </div>
            </StaggerItem>
          )
        })}
      </StaggerContainer>
    </div>
  )
}
