import { useRef, useEffect, useState, useCallback, useMemo } from 'react'

const CLUSTER_COLORS = [
  '#6366f1', '#1DB954', '#f59e0b', '#ec4899', '#06b6d4',
  '#8b5cf6', '#ef4444', '#10b981', '#f97316', '#14b8a6',
]

function formatFollowers(n) {
  if (!n) return '\u2014'
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`
  if (n >= 1_000) return `${(n / 1_000).toFixed(0)}K`
  return String(n)
}

export default function ArtistNetwork({ nodes = [], edges = [], clusters = [], clusterNames = {}, title = 'Ecosistema Artisti', loading = false, genreNodes = [], genreEdges = [] }) {
  const svgRef = useRef(null)
  const containerRef = useRef(null)
  const animRef = useRef(null)
  const [tooltip, setTooltip] = useState(null)
  const [positions, setPositions] = useState([])
  const posRef = useRef([])
  const velRef = useRef([])

  // Zoom + Pan state
  const [transform, setTransform] = useState({ x: 0, y: 0, scale: 1 })
  const [isDragging, setIsDragging] = useState(false)
  const dragStart = useRef({ x: 0, y: 0 })

  // Semantic zoom blend factor: 0 at scale <= 1.2, 1 at scale >= 2.0
  const zoomBlend = Math.max(0, Math.min(1, (transform.scale - 1.2) / 0.8))

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

  // Combined index for artists + genre nodes
  const nodeIndex = useMemo(() => {
    const map = {}
    nodes.forEach((n, i) => { map[n.id] = i })
    genreNodes.forEach((gn, i) => { map[gn.id] = nodes.length + i })
    return map
  }, [nodes, genreNodes])

  // Artist-only index for artist-to-artist edges
  const artistIndex = useMemo(() => {
    const map = {}
    nodes.forEach((n, i) => { map[n.id] = i })
    return map
  }, [nodes])

  // Stable data key for simulation restart detection
  const dataKey = useMemo(() => {
    const nids = nodes.map(n => n.id).sort().join(',')
    const gnids = genreNodes.map(g => g.id).sort().join(',')
    const geids = genreEdges.map(e => `${e.source}-${e.target}`).sort().join(',')
    return `${nids}|${gnids}|${geids}`
  }, [nodes, genreNodes, genreEdges])
  const prevDataKeyRef = useRef(null)

  // Unified simulation: artists + genres, KG physics
  useEffect(() => {
    if (animRef.current) cancelAnimationFrame(animRef.current)
    if (nodes.length === 0) return
    if (prevDataKeyRef.current === dataKey) return
    prevDataKeyRef.current = dataKey

    const width = 700
    const height = 500
    const cx = width / 2
    const cy = height / 2

    const hasGenres = genreNodes.length > 0
    const totalNodes = nodes.length + genreNodes.length

    // Init: genre nodes in a ring near center, artists scattered
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

    posRef.current = initPos
    velRef.current = initVel
    setPositions([...initPos])

    let frameCount = 0
    const maxFrames = 400
    const damping = 0.82
    const artistRepulsion = 600
    const genreRepulsion = hasGenres ? 3000 : 800
    const genreArtistRepulsion = 400
    const attraction = hasGenres ? 0.01 : 0.008
    const centerForce = 0.015

    const isGenre = (idx) => idx >= nodes.length

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

      // Attraction: genre-artist edges
      for (const edge of genreEdges) {
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
        forces[ti].x -= fx * 0.1
        forces[ti].y -= fy * 0.1
      }

      // Attraction: artist-artist edges (keeps related artists closer)
      for (const edge of edges) {
        const si = artistIndex[edge.source]
        const ti = artistIndex[edge.target]
        if (si === undefined || ti === undefined) continue
        const dx = pos[ti].x - pos[si].x
        const dy = pos[ti].y - pos[si].y
        const dist = Math.sqrt(dx * dx + dy * dy) || 1
        const force = dist * 0.005
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
        setPositions(pos.map(p => ({ ...p })))
      }

      animRef.current = requestAnimationFrame(simulate)
    }

    animRef.current = requestAnimationFrame(simulate)

    return () => {
      if (animRef.current) cancelAnimationFrame(animRef.current)
    }
  // Suppressed: nodes/genreNodes/genreEdges/edges are unstable array props; dataKey (derived string)
  // already captures their identity, and adding them would restart the simulation on every render.
  }, [dataKey, nodeIndex, artistIndex]) // eslint-disable-line react-hooks/exhaustive-deps

  // Zoom: wheel handler (zoom toward cursor)
  const handleWheel = useCallback((e) => {
    e.preventDefault()
    const container = containerRef.current
    if (!container) return
    const rect = container.getBoundingClientRect()
    const mouseX = e.clientX - rect.left
    const mouseY = e.clientY - rect.top

    const scaleFactor = e.deltaY > 0 ? 0.9 : 1.1

    setTransform(prev => {
      const newScale = Math.max(0.5, Math.min(4, prev.scale * scaleFactor))
      // Zoom towards mouse position
      const svgX = (mouseX - prev.x) / prev.scale
      const svgY = (mouseY - prev.y) / prev.scale
      const newX = mouseX - svgX * newScale
      const newY = mouseY - svgY * newScale
      return { x: newX, y: newY, scale: newScale }
    })
  }, [])

  // Pan: drag handlers
  const handleMouseDown = useCallback((e) => {
    // Don't pan when clicking nodes
    if (e.target.closest('.artist-node, circle[role="button"]')) return
    setIsDragging(true)
    setTransform(prev => {
      dragStart.current = { x: e.clientX - prev.x, y: e.clientY - prev.y }
      return prev
    })
  }, [])

  const handleMouseMove = useCallback((e) => {
    if (!isDragging) return
    setTransform(prev => ({
      ...prev,
      x: e.clientX - dragStart.current.x,
      y: e.clientY - dragStart.current.y,
    }))
  }, [isDragging])

  const handleMouseUp = useCallback(() => setIsDragging(false), [])

  // Attach wheel listener with passive: false to allow preventDefault
  useEffect(() => {
    const container = containerRef.current
    if (!container) return
    container.addEventListener('wheel', handleWheel, { passive: false })
    return () => container.removeEventListener('wheel', handleWheel)
  }, [handleWheel])

  // Mouse up on window (handles drag release outside container)
  useEffect(() => {
    if (!isDragging) return
    const handleGlobalUp = () => setIsDragging(false)
    window.addEventListener('mouseup', handleGlobalUp)
    return () => window.removeEventListener('mouseup', handleGlobalUp)
  }, [isDragging])

  const handleArtistMouseEnter = useCallback((node, pos) => {
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

  return (
    <div className="glow-card bg-surface rounded-xl p-5 relative">
      <h3 className="text-text-primary font-display font-semibold mb-4">{title}</h3>
      <div className="w-full max-w-[700px] mx-auto">
        <div
          ref={containerRef}
          style={{ overflow: 'hidden', cursor: isDragging ? 'grabbing' : 'grab' }}
          onMouseDown={handleMouseDown}
          onMouseMove={handleMouseMove}
          onMouseUp={handleMouseUp}
        >
          <svg
            ref={svgRef}
            viewBox="0 0 700 500"
            className="w-full h-auto"
            style={{ maxHeight: '500px' }}
            role="img"
            aria-label="Grafo unificato artisti e generi"
          >
            <g transform={`translate(${transform.x}, ${transform.y}) scale(${transform.scale})`}>
              {/* Layer 1: Genre-artist edges — fade with zoom */}
              {genreEdges.map((edge, i) => {
                const si = nodeIndex[edge.source]
                const ti = nodeIndex[edge.target]
                if (si === undefined || ti === undefined || !positions[si] || !positions[ti]) return null
                const opacity = 0.15 * (1 - zoomBlend * 0.67)
                if (opacity < 0.01) return null
                return (
                  <line
                    key={`ge-${i}`}
                    x1={positions[si].x}
                    y1={positions[si].y}
                    x2={positions[ti].x}
                    y2={positions[ti].y}
                    stroke="#ffffff"
                    strokeOpacity={opacity}
                    strokeWidth={0.5}
                  />
                )
              })}

              {/* Layer 2: Artist-artist edges — appear with zoom */}
              {edges.map((edge, i) => {
                const si = artistIndex[edge.source]
                const ti = artistIndex[edge.target]
                if (si === undefined || ti === undefined || !positions[si] || !positions[ti]) return null
                const baseOpacity = 0.04 + (edge.weight || 0) * 0.12
                const opacity = baseOpacity * zoomBlend
                if (opacity < 0.01) return null
                return (
                  <line
                    key={`ae-${i}`}
                    x1={positions[si].x}
                    y1={positions[si].y}
                    x2={positions[ti].x}
                    y2={positions[ti].y}
                    stroke="#ffffff"
                    strokeOpacity={opacity}
                    strokeWidth={0.5 + (edge.weight || 0) * 1.5}
                  />
                )
              })}

              {/* Layer 3: Artist nodes — size interpolates between KG-small and Rete-large */}
              {nodes.map((node, i) => {
                if (!positions[i]) return null
                const color = clusterColorMap[node.id] || '#6366f1'
                const pr = node.pagerank || 0

                // KG size: small (4-8), Rete size: large (5-18 based on pagerank)
                const kgR = Math.max(4, Math.min(8, 4 + pr * 100))
                const reteR = Math.max(5, Math.min(18, 5 + pr * 200))
                const r = kgR + (reteR - kgR) * zoomBlend

                // KG opacity: moderate, Rete opacity: full based on pagerank
                const kgOpacity = Math.max(0.5, Math.min(0.9, 0.4 + pr * 8))
                const reteOpacity = Math.max(0.4, Math.min(0.95, 0.3 + pr * 10))
                const fillOpacity = kgOpacity + (reteOpacity - kgOpacity) * zoomBlend

                // Show glow ring for top artists when zoomed in
                const showGlow = pr > 0.02 && zoomBlend > 0.3
                // Show stroke for top artists when zoomed in
                const showStroke = pr > 0.02 && zoomBlend > 0.3

                return (
                  <g key={node.id}>
                    {showGlow && (
                      <circle
                        cx={positions[i].x}
                        cy={positions[i].y}
                        r={r + 3}
                        fill={color}
                        fillOpacity={0.15 * zoomBlend}
                      />
                    )}
                    <circle
                      cx={positions[i].x}
                      cy={positions[i].y}
                      r={r}
                      fill={color}
                      fillOpacity={fillOpacity}
                      stroke={showStroke ? '#ffffff' : 'none'}
                      strokeWidth={showStroke ? 1.5 : 0}
                      className="artist-node cursor-pointer"
                      role="button"
                      tabIndex={0}
                      aria-label={node.name}
                      onMouseEnter={() => handleArtistMouseEnter(node, positions[i])}
                      onMouseLeave={handleMouseLeave}
                      onKeyDown={(e) => {
                        if (e.key === 'Enter' || e.key === ' ') {
                          e.preventDefault()
                          handleArtistMouseEnter(node, positions[i])
                        }
                      }}
                      onBlur={handleMouseLeave}
                    />
                  </g>
                )
              })}

              {/* Layer 4: Genre nodes — fade with zoom */}
              {genreNodes.map((gn, gi) => {
                const posIdx = nodes.length + gi
                if (!positions[posIdx]) return null
                const clusterIdx = gn.cluster ?? 0
                const color = CLUSTER_COLORS[clusterIdx % CLUSTER_COLORS.length]
                const r = Math.max(22, Math.min(28, 18 + (gn.artist_count || 1) * 1.2))
                const pos = positions[posIdx]
                const genreOpacity = 1 - zoomBlend * 0.8

                return (
                  <g key={gn.id} opacity={genreOpacity}>
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

              {/* Layer 5: Artist labels — appear when zoomed in for top artists */}
              {zoomBlend > 0.3 && nodes.map((node, i) => {
                if (!((node.pagerank || 0) > 0.02) || !positions[i]) return null
                const labelOpacity = Math.min(1, (zoomBlend - 0.3) / 0.3)
                return (
                  <text
                    key={`label-${node.id}`}
                    x={positions[i].x}
                    y={positions[i].y - 16}
                    textAnchor="middle"
                    fill="#e0e0e0"
                    fillOpacity={labelOpacity}
                    fontSize={10}
                    fontFamily="Inter, sans-serif"
                    fontWeight={500}
                    pointerEvents="none"
                  >
                    {node.name.length > 15 ? node.name.slice(0, 15) + '\u2026' : node.name}
                  </text>
                )
              })}
            </g>
          </svg>
        </div>
      </div>

      {/* Tooltip — positioned relative to the card, not the SVG transform */}
      {tooltip && (
        <div
          className="absolute bg-surface-hover border border-border rounded-lg px-3 py-2 pointer-events-none z-10 shadow-lg min-w-[180px]"
          style={{
            left: `${(tooltip.x * transform.scale + transform.x) / (containerRef.current?.clientWidth || 700) * 100}%`,
            top: `${(tooltip.y * transform.scale + transform.y) / (containerRef.current?.clientHeight || 500) * 100 - 8}%`,
            transform: 'translate(-50%, -100%)',
          }}
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
                {tooltip.connections > 0 && <span>{tooltip.connections} conn.</span>}
                {tooltip.betweenness > 0.01 && <span>Ponte: {Math.round(tooltip.betweenness * 100)}%</span>}
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
