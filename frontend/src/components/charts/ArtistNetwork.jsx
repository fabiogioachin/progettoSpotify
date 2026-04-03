import { useRef, useEffect, useState, useCallback, useMemo } from 'react'

const CLUSTER_COLORS = [
  '#6366f1', '#1DB954', '#f59e0b', '#ec4899', '#06b6d4',
  '#8b5cf6', '#ef4444', '#10b981', '#f97316', '#14b8a6',
]

function formatFollowers(n) {
  if (!n) return '—'
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`
  if (n >= 1_000) return `${(n / 1_000).toFixed(0)}K`
  return String(n)
}

export default function ArtistNetwork({ nodes = [], edges = [], clusters = [], clusterNames = {}, title = 'Ecosistema Artisti', loading = false, viewMode = 'rete', genreNodes = [], genreEdges = [] }) {
  const svgRef = useRef(null)
  const animRef = useRef(null)
  const [tooltip, setTooltip] = useState(null)
  const [positions, setPositions] = useState([])
  const posRef = useRef([])
  const velRef = useRef([])

  // KG simulation state — separate from rete simulation
  const [kgPositions, setKgPositions] = useState([])
  const kgPosRef = useRef([])
  const kgVelRef = useRef([])
  const kgAnimRef = useRef(null)

  // Build cluster color map and node-to-cluster map
  const clusterColorMap = useMemo(() => {
    const map = {}
    clusters.forEach(c => {
      map[c.id] = CLUSTER_COLORS[c.cluster % CLUSTER_COLORS.length]
    })
    return map
  }, [clusters])

  const nodeClusterMap = useMemo(() => {
    const map = {}
    clusters.forEach(c => { map[c.id] = c.cluster })
    return map
  }, [clusters])

  // Build node index map
  const nodeIndex = useMemo(() => {
    const map = {}
    nodes.forEach((n, i) => { map[n.id] = i })
    return map
  }, [nodes])

  // Stable data key to avoid restarting simulation when references change but data is the same
  const dataKey = useMemo(() => {
    const nodeIds = nodes.map(n => n.id).sort().join(',')
    const edgeIds = edges.map(e => `${e.source}-${e.target}`).sort().join(',')
    return `${nodeIds}|${edgeIds}`
  }, [nodes, edges])
  const prevDataKeyRef = useRef(null)

  // KG: combined index for artists + genre nodes
  const kgNodeIndex = useMemo(() => {
    const map = {}
    nodes.forEach((n, i) => { map[n.id] = i })
    genreNodes.forEach((gn, i) => { map[gn.id] = nodes.length + i })
    return map
  }, [nodes, genreNodes])

  const kgDataKey = useMemo(() => {
    const nids = nodes.map(n => n.id).sort().join(',')
    const gnids = genreNodes.map(g => g.id).sort().join(',')
    const geids = genreEdges.map(e => `${e.source}-${e.target}`).sort().join(',')
    return `${nids}|${gnids}|${geids}`
  }, [nodes, genreNodes, genreEdges])
  const prevKgDataKeyRef = useRef(null)

  // KG simulation
  useEffect(() => {
    // Always cancel any running KG animation first (prevents leak on mode switch)
    if (kgAnimRef.current) cancelAnimationFrame(kgAnimRef.current)
    if (viewMode !== 'kg') return
    if (nodes.length === 0 || genreNodes.length === 0) return
    if (prevKgDataKeyRef.current === kgDataKey) return
    prevKgDataKeyRef.current = kgDataKey

    const width = 700
    const height = 500
    const cx = width / 2
    const cy = height / 2

    const totalNodes = nodes.length + genreNodes.length

    // Init: genre nodes start near center, artists scattered
    const initPos = [
      ...nodes.map(() => ({
        x: cx + (Math.random() - 0.5) * 400,
        y: cy + (Math.random() - 0.5) * 350,
      })),
      ...genreNodes.map((_, gi) => {
        const angle = (gi / genreNodes.length) * Math.PI * 2
        return {
          x: cx + Math.cos(angle) * 150,
          y: cy + Math.sin(angle) * 120,
        }
      }),
    ]
    const initVel = Array.from({ length: totalNodes }, () => ({ x: 0, y: 0 }))

    kgPosRef.current = initPos
    kgVelRef.current = initVel
    setKgPositions([...initPos])

    let frameCount = 0
    const maxFrames = 400
    const damping = 0.82
    const artistRepulsion = 600
    const genreRepulsion = 3000  // genre nodes repel each other strongly
    const genreArtistRepulsion = 400
    const attraction = 0.01      // genre-artist edge attraction
    const centerForce = 0.015

    const isGenre = (idx) => idx >= nodes.length

    function simulate() {
      if (frameCount >= maxFrames) return

      const pos = kgPosRef.current
      const vel = kgVelRef.current
      const n = pos.length
      const forces = pos.map(() => ({ x: 0, y: 0 }))

      // Repulsion (all pairs)
      for (let i = 0; i < n; i++) {
        for (let j = i + 1; j < n; j++) {
          const dx = pos[i].x - pos[j].x
          const dy = pos[i].y - pos[j].y
          const dist = Math.sqrt(dx * dx + dy * dy) || 1

          let repulsion
          if (isGenre(i) && isGenre(j)) {
            repulsion = genreRepulsion
          } else if (isGenre(i) || isGenre(j)) {
            repulsion = genreArtistRepulsion
          } else {
            repulsion = artistRepulsion
          }

          const force = repulsion / (dist * dist)
          const fx = (dx / dist) * force
          const fy = (dy / dist) * force
          forces[i].x += fx
          forces[i].y += fy
          forces[j].x -= fx
          forces[j].y -= fy
        }
      }

      // Attraction: genre edges only
      for (const edge of genreEdges) {
        const si = kgNodeIndex[edge.source]
        const ti = kgNodeIndex[edge.target]
        if (si === undefined || ti === undefined) continue
        const dx = pos[ti].x - pos[si].x
        const dy = pos[ti].y - pos[si].y
        const dist = Math.sqrt(dx * dx + dy * dy) || 1
        const force = dist * attraction
        const fx = (dx / dist) * force
        const fy = (dy / dist) * force
        // Genre node (target) pulls artist, artist barely pulls genre
        forces[si].x += fx
        forces[si].y += fy
        forces[ti].x -= fx * 0.1
        forces[ti].y -= fy * 0.1
      }

      // Center gravity
      for (let i = 0; i < n; i++) {
        forces[i].x += (cx - pos[i].x) * centerForce
        forces[i].y += (cy - pos[i].y) * centerForce
      }

      // Update
      for (let i = 0; i < n; i++) {
        vel[i].x = (vel[i].x + forces[i].x) * damping
        vel[i].y = (vel[i].y + forces[i].y) * damping
        pos[i].x += vel[i].x
        pos[i].y += vel[i].y
        pos[i].x = Math.max(30, Math.min(width - 30, pos[i].x))
        pos[i].y = Math.max(30, Math.min(height - 30, pos[i].y))
      }

      frameCount++
      if (frameCount % 3 === 0) {
        setKgPositions(pos.map(p => ({ ...p })))
      }

      kgAnimRef.current = requestAnimationFrame(simulate)
    }

    kgAnimRef.current = requestAnimationFrame(simulate)

    return () => {
      if (kgAnimRef.current) cancelAnimationFrame(kgAnimRef.current)
    }
  // Suppressed: genreNodes/genreEdges are unstable array props; kgDataKey (derived string)
  // already captures their identity, and adding them would restart the simulation on every render.
  }, [viewMode, kgDataKey, kgNodeIndex]) // eslint-disable-line react-hooks/exhaustive-deps

  // Initialize positions
  useEffect(() => {
    if (nodes.length === 0) return
    // Skip simulation restart if the actual data hasn't changed
    if (prevDataKeyRef.current === dataKey) return
    prevDataKeyRef.current = dataKey

    const width = 700
    const height = 500
    const cx = width / 2
    const cy = height / 2

    const initPos = nodes.map(() => ({
      x: cx + (Math.random() - 0.5) * 300,
      y: cy + (Math.random() - 0.5) * 250,
    }))
    const initVel = nodes.map(() => ({ x: 0, y: 0 }))

    posRef.current = initPos
    velRef.current = initVel
    setPositions([...initPos])

    let frameCount = 0
    const maxFrames = 300
    const damping = 0.85
    const repulsion = 800
    const attraction = 0.008
    const centerForce = 0.01

    function simulate() {
      if (frameCount >= maxFrames) return

      const pos = posRef.current
      const vel = velRef.current
      const n = pos.length

      const forces = pos.map(() => ({ x: 0, y: 0 }))

      // Repulsion (all pairs)
      for (let i = 0; i < n; i++) {
        for (let j = i + 1; j < n; j++) {
          const dx = pos[i].x - pos[j].x
          const dy = pos[i].y - pos[j].y
          const dist = Math.sqrt(dx * dx + dy * dy) || 1
          const force = repulsion / (dist * dist)
          const fx = (dx / dist) * force
          const fy = (dy / dist) * force
          forces[i].x += fx
          forces[i].y += fy
          forces[j].x -= fx
          forces[j].y -= fy
        }
      }

      // Attraction (edges)
      for (const edge of edges) {
        const si = nodeIndex[edge.source]
        const ti = nodeIndex[edge.target]
        if (si === undefined || ti === undefined) continue
        const dx = pos[ti].x - pos[si].x
        const dy = pos[ti].y - pos[si].y
        const dist = Math.sqrt(dx * dx + dy * dy) || 1
        const force = dist * attraction
        const fx = (dx / dist) * force
        const fy = (dy / dist) * force
        forces[si].x += fx
        forces[si].y += fy
        forces[ti].x -= fx
        forces[ti].y -= fy
      }

      // Center gravity
      for (let i = 0; i < n; i++) {
        forces[i].x += (cx - pos[i].x) * centerForce
        forces[i].y += (cy - pos[i].y) * centerForce
      }

      // Update velocities and positions
      for (let i = 0; i < n; i++) {
        vel[i].x = (vel[i].x + forces[i].x) * damping
        vel[i].y = (vel[i].y + forces[i].y) * damping
        pos[i].x += vel[i].x
        pos[i].y += vel[i].y
        pos[i].x = Math.max(20, Math.min(width - 20, pos[i].x))
        pos[i].y = Math.max(20, Math.min(height - 20, pos[i].y))
      }

      frameCount++
      if (frameCount % 3 === 0) {
        setPositions(pos.map(p => ({ ...p })))
      }

      animRef.current = requestAnimationFrame(simulate)
    }

    animRef.current = requestAnimationFrame(simulate)

    return () => {
      if (animRef.current) cancelAnimationFrame(animRef.current)
    }
  // Suppressed: nodes/edges are unstable array props; dataKey (derived string)
  // already captures their identity, and adding them would restart the simulation on every render.
  }, [dataKey, nodeIndex]) // eslint-disable-line react-hooks/exhaustive-deps

  const handleMouseEnter = useCallback((node, pos) => {
    const clusterId = nodeClusterMap[node.id]
    const clusterLabel = clusterId != null ? (clusterNames[clusterId] || `Cerchia ${clusterId + 1}`) : null
    setTooltip({ ...node, x: pos.x, y: pos.y, clusterLabel })
  }, [nodeClusterMap, clusterNames])

  const handleGenreMouseEnter = useCallback((genreNode, pos) => {
    setTooltip({
      ...genreNode,
      x: pos.x,
      y: pos.y,
      isGenreNode: true,
    })
  }, [])

  const handleMouseLeave = useCallback(() => {
    setTooltip(null)
  }, [])

  if (loading) {
    return (
      <div className="glow-card bg-surface rounded-xl p-5">
        <h3 className="text-text-primary font-display font-semibold mb-4">{title}</h3>
        <div className="h-[500px] flex items-center justify-center">
          <div className="w-8 h-8 border-2 border-accent border-t-transparent rounded-full animate-spin" />
        </div>
      </div>
    )
  }

  if (!nodes.length) {
    return null
  }

  if (viewMode === 'kg') {
    return (
      <div className="glow-card bg-surface rounded-xl p-5 relative">
        <h3 className="text-text-primary font-display font-semibold mb-4">{title}</h3>
        <svg viewBox="0 0 700 500" className="w-full h-auto" style={{ maxHeight: '500px' }} role="img" aria-label="Knowledge graph generi e artisti">
          {/* Genre edges only */}
          {genreEdges.map((edge, i) => {
            const si = kgNodeIndex[edge.source]
            const ti = kgNodeIndex[edge.target]
            if (si === undefined || ti === undefined || !kgPositions[si] || !kgPositions[ti]) return null
            return (
              <line
                key={`kge-${i}`}
                x1={kgPositions[si].x}
                y1={kgPositions[si].y}
                x2={kgPositions[ti].x}
                y2={kgPositions[ti].y}
                stroke="#ffffff"
                strokeOpacity={0.15}
                strokeWidth={0.5}
              />
            )
          })}
          {/* Artist nodes (KG: smaller, capped) */}
          {nodes.map((node, i) => {
            if (!kgPositions[i]) return null
            const color = clusterColorMap[node.id] || '#6366f1'
            const pr = node.pagerank || 0
            const r = Math.max(4, Math.min(8, 4 + pr * 100))
            return (
              <circle
                key={node.id}
                cx={kgPositions[i].x}
                cy={kgPositions[i].y}
                r={r}
                fill={color}
                fillOpacity={Math.max(0.5, Math.min(0.9, 0.4 + pr * 8))}
                className="cursor-pointer"
                role="button"
                tabIndex={0}
                aria-label={node.name}
                onMouseEnter={() => handleMouseEnter(node, kgPositions[i])}
                onMouseLeave={handleMouseLeave}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' || e.key === ' ') {
                    e.preventDefault()
                    handleMouseEnter(node, kgPositions[i])
                  }
                }}
                onBlur={handleMouseLeave}
              />
            )
          })}
          {/* Genre nodes — rendered on top of artist nodes */}
          {genreNodes.map((gn, gi) => {
            const posIdx = nodes.length + gi
            if (!kgPositions[posIdx]) return null
            const clusterIdx = gn.cluster ?? 0
            const color = CLUSTER_COLORS[clusterIdx % CLUSTER_COLORS.length]
            const r = Math.max(22, Math.min(28, 18 + (gn.artist_count || 1) * 1.2))
            const pos = kgPositions[posIdx]
            return (
              <g key={gn.id}>
                {/* Outer glow ring */}
                <circle
                  cx={pos.x}
                  cy={pos.y}
                  r={r + 4}
                  fill={color}
                  fillOpacity={0.08}
                />
                {/* Main genre circle */}
                <circle
                  cx={pos.x}
                  cy={pos.y}
                  r={r}
                  fill={color}
                  fillOpacity={0.2}
                  stroke={color}
                  strokeWidth={2}
                  className="cursor-pointer"
                  role="button"
                  tabIndex={0}
                  aria-label={`Genere: ${gn.name}`}
                  onMouseEnter={() => handleGenreMouseEnter(gn, pos)}
                  onMouseLeave={handleMouseLeave}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter' || e.key === ' ') {
                      e.preventDefault()
                      handleGenreMouseEnter(gn, pos)
                    }
                  }}
                  onBlur={handleMouseLeave}
                />
                {/* Genre label */}
                <text
                  x={pos.x}
                  y={pos.y + 4}
                  textAnchor="middle"
                  fill="#ffffff"
                  fontSize={11}
                  fontFamily="Inter, sans-serif"
                  fontWeight={600}
                  pointerEvents="none"
                >
                  {gn.name.length > 12 ? gn.name.slice(0, 12) + '\u2026' : gn.name}
                </text>
              </g>
            )
          })}
        </svg>
        {/* Tooltip */}
        {tooltip && (
          <div
            className="absolute bg-surface-hover border border-border rounded-lg px-3 py-2 pointer-events-none z-10 shadow-lg min-w-[180px]"
            style={{ left: `${(tooltip.x / 700) * 100}%`, top: `${(tooltip.y / 500) * 100 - 8}%`, transform: 'translate(-50%, -100%)' }}
          >
            {tooltip.isGenreNode ? (
              <>
                <p className="text-text-primary text-sm font-semibold">{tooltip.name}</p>
                <p className="text-accent text-xs font-medium">{tooltip.artist_count} artisti in questa cerchia</p>
              </>
            ) : (
              <>
                <p className="text-text-primary text-sm font-semibold">{tooltip.name}</p>
                {tooltip.is_top && <p className="text-accent text-xs font-medium">Top Artist</p>}
                {tooltip.pagerank > 0 && (
                  <p className="text-accent text-xs font-medium">
                    Influenza: {Math.round(tooltip.pagerank * 100)}%
                  </p>
                )}
                {tooltip.clusterLabel && (
                  <p className="text-text-secondary text-xs mt-0.5">{tooltip.clusterLabel}</p>
                )}
                {tooltip.genres && tooltip.genres.length > 0 && (
                  <p className="text-text-muted text-xs mt-1">{tooltip.genres.join(', ')}</p>
                )}
                <div className="flex items-center gap-3 mt-1 text-xs text-text-secondary">
                  {tooltip.popularity > 0 && <span>Pop. {tooltip.popularity}</span>}
                  {tooltip.followers > 0 && <span>{formatFollowers(tooltip.followers)} follower</span>}
                </div>
              </>
            )}
          </div>
        )}
        {/* Cluster Legend */}
        <div className="flex flex-wrap gap-3 mt-3">
          {[...new Set(clusters.map(c => c.cluster))]
            .filter(clusterId => clusterNames[clusterId])
            .map(clusterId => (
              <div key={clusterId} className="flex items-center gap-1.5">
                <div className="w-3 h-3 rounded-full" style={{ backgroundColor: CLUSTER_COLORS[clusterId % CLUSTER_COLORS.length] }} />
                <span className="text-text-muted text-xs">{clusterNames[clusterId]}</span>
              </div>
            ))}
        </div>
      </div>
    )
  }

  // Default: "rete" view — unchanged
  return (
    <div className="glow-card bg-surface rounded-xl p-5 relative">
      <h3 className="text-text-primary font-display font-semibold mb-4">{title}</h3>
      <svg ref={svgRef} viewBox="0 0 700 500" className="w-full h-auto" style={{ maxHeight: '500px' }} role="img" aria-label="Grafo delle connessioni tra artisti">
        {/* Edges */}
        {edges.map((edge, i) => {
          const si = nodeIndex[edge.source]
          const ti = nodeIndex[edge.target]
          if (si === undefined || ti === undefined || !positions[si] || !positions[ti]) return null
          return (
            <line
              key={`e-${i}`}
              x1={positions[si].x}
              y1={positions[si].y}
              x2={positions[ti].x}
              y2={positions[ti].y}
              stroke="#ffffff"
              strokeOpacity={0.04 + (edge.weight || 0) * 0.12}
              strokeWidth={0.5 + (edge.weight || 0) * 1.5}
            />
          )
        })}
        {/* Nodes */}
        {nodes.map((node, i) => {
          if (!positions[i]) return null
          const color = clusterColorMap[node.id] || '#6366f1'
          const pr = node.pagerank || 0
          const r = Math.max(4, Math.min(18, 5 + pr * 200))
          return (
            <g key={node.id}>
              {pr > 0.02 && (
                <circle
                  cx={positions[i].x}
                  cy={positions[i].y}
                  r={r + 3}
                  fill={color}
                  fillOpacity={0.15}
                />
              )}
              <circle
                cx={positions[i].x}
                cy={positions[i].y}
                r={r}
                fill={color}
                fillOpacity={Math.max(0.4, Math.min(0.95, 0.3 + pr * 10))}
                stroke={pr > 0.02 ? '#ffffff' : 'none'}
                strokeWidth={pr > 0.02 ? 1.5 : 0}
                className="artist-node cursor-pointer"
                role="button"
                tabIndex={0}
                aria-label={node.name}
                onMouseEnter={() => handleMouseEnter(node, positions[i])}
                onMouseLeave={handleMouseLeave}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' || e.key === ' ') {
                    e.preventDefault()
                    handleMouseEnter(node, positions[i])
                  }
                }}
                onBlur={handleMouseLeave}
              />
            </g>
          )
        })}
        {/* Node labels for top artists */}
        {nodes.map((node, i) => {
          if (!((node.pagerank || 0) > 0.02) || !positions[i]) return null
          return (
            <text
              key={`label-${node.id}`}
              x={positions[i].x}
              y={positions[i].y - 16}
              textAnchor="middle"
              fill="#e0e0e0"
              fontSize={10}
              fontFamily="Inter, sans-serif"
              fontWeight={500}
            >
              {node.name.length > 15 ? node.name.slice(0, 15) + '\u2026' : node.name}
            </text>
          )
        })}
      </svg>
      {/* Tooltip */}
      {tooltip && (
        <div
          className="absolute bg-surface-hover border border-border rounded-lg px-3 py-2 pointer-events-none z-10 shadow-lg min-w-[180px]"
          style={{ left: `${(tooltip.x / 700) * 100}%`, top: `${(tooltip.y / 500) * 100 - 8}%`, transform: 'translate(-50%, -100%)' }}
        >
          <p className="text-text-primary text-sm font-semibold">{tooltip.name}</p>
          {tooltip.is_top && <p className="text-accent text-xs font-medium">Top Artist</p>}
          {tooltip.pagerank > 0 && (
            <p className="text-accent text-xs font-medium">
              Influenza: {Math.round(tooltip.pagerank * 100)}%
            </p>
          )}
          {tooltip.clusterLabel && (
            <p className="text-text-secondary text-xs mt-0.5">{tooltip.clusterLabel}</p>
          )}
          {tooltip.genres && tooltip.genres.length > 0 && (
            <p className="text-text-muted text-xs mt-1">
              {tooltip.genres.join(', ')}
            </p>
          )}
          <div className="flex items-center gap-3 mt-1 text-xs text-text-secondary">
            {tooltip.popularity > 0 && (
              <span>Pop. {tooltip.popularity}</span>
            )}
            {tooltip.followers > 0 && (
              <span>{formatFollowers(tooltip.followers)} follower</span>
            )}
            {tooltip.connections > 0 && (
              <span>{tooltip.connections} conn.</span>
            )}
            {tooltip.betweenness > 0.01 && (
              <span>Ponte: {Math.round(tooltip.betweenness * 100)}%</span>
            )}
          </div>
        </div>
      )}
      {/* Cluster Legend */}
      <div className="flex flex-wrap gap-3 mt-3">
        {[...new Set(clusters.map(c => c.cluster))]
          .filter(clusterId => clusterNames[clusterId])
          .map(clusterId => (
            <div key={clusterId} className="flex items-center gap-1.5">
              <div className="w-3 h-3 rounded-full" style={{ backgroundColor: CLUSTER_COLORS[clusterId % CLUSTER_COLORS.length] }} />
              <span className="text-text-muted text-xs">{clusterNames[clusterId]}</span>
            </div>
          ))}
      </div>
    </div>
  )
}
