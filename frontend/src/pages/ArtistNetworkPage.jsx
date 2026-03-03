import { useSpotifyData } from '../hooks/useSpotifyData'
import KPICard from '../components/cards/KPICard'
import ArtistNetwork from '../components/charts/ArtistNetwork'
import LoadingSpinner from '../components/ui/LoadingSpinner'
import { Users, GitBranch, Waypoints, BarChart3, RefreshCw } from 'lucide-react'

export default function ArtistNetworkPage() {
  const { data, loading, error, refetch } = useSpotifyData('/api/artist-network')

  const metrics = data?.metrics || {}
  const nodes = data?.nodes || []
  const edges = data?.edges || []
  const clusters = data?.clusters || []
  const bridges = data?.bridges || []

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
          <LoadingSpinner />
        ) : (
          <>
            {/* KPI Cards */}
            <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-4">
              <KPICard title="Artisti nel Grafo" value={metrics.total_nodes || 0} icon={Users} delay={0} />
              <KPICard title="Connessioni" value={metrics.total_edges || 0} icon={GitBranch} delay={100} />
              <KPICard title="Cluster" value={metrics.cluster_count || 0} icon={Waypoints} delay={200} />
              <KPICard title="Top Artists" value={metrics.top_artists_count || 0} icon={BarChart3} delay={300} />
            </div>

            {/* Network Graph */}
            <ArtistNetwork nodes={nodes} edges={edges} clusters={clusters} loading={loading} />

            {/* Bridge Artists */}
            {bridges.length > 0 && (
              <div className="glow-card bg-surface rounded-xl p-5">
                <h3 className="text-text-primary font-display font-semibold mb-4 flex items-center gap-2">
                  <Waypoints size={18} className="text-accent" />
                  Bridge Artists
                </h3>
                <p className="text-text-secondary text-sm mb-4">
                  Artisti che collegano cluster di gusto diversi
                </p>
                <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-3">
                  {bridges.map((bridge, i) => (
                    <div key={bridge.id} className="flex items-center gap-3 p-3 rounded-lg bg-surface-hover animate-slide-up" style={{ animationDelay: `${i * 100}ms` }}>
                      {bridge.image ? (
                        <img src={bridge.image} alt={bridge.name} className="w-12 h-12 rounded-full object-cover flex-shrink-0" />
                      ) : (
                        <div className="w-12 h-12 rounded-full bg-background flex items-center justify-center flex-shrink-0">
                          <Users size={18} className="text-text-muted" />
                        </div>
                      )}
                      <div className="min-w-0">
                        <p className="text-text-primary text-sm font-medium truncate">{bridge.name}</p>
                        <p className="text-accent text-xs">{bridge.bridge_score} connessioni cross-cluster</p>
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
