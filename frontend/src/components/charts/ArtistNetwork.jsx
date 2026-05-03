import { useRef, useEffect, useState, useCallback, useMemo } from 'react'

const CLUSTER_COLORS = [
  '#6366f1', '#1DB954', '#f59e0b', '#ec4899', '#06b6d4',
  '#8b5cf6', '#ef4444', '#10b981', '#f97316', '#14b8a6',
]

const VB_W = 960
const VB_H = 540

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

  // Zoom + Pan — rendered transform + smooth target
  const [transform, setTransform] = useState({ x: 0, y: 0, scale: 1 })
  const [isDragging, setIsDragging] = useState(false)
  const dragStart = useRef({ x: 0, y: 0 })
  const targetRef = useRef({ x: 0, y: 0, scale: 1 })
  const zoomAnimRef = useRef(null)

  // Smooth zoom animation via rAF lerp
  const animateZoom = useCallback(() => {
    const target = targetRef.current
    setTransform(prev => {
      const factor = 0.22
      const nx = prev.x + (target.x - prev.x) * factor
      const ny = prev.y + (target.y - prev.y) * factor
      const ns = prev.scale + (target.scale - prev.scale) * factor

      const converged =
        Math.abs(target.x - nx) < 0.3 &&
        Math.abs(target.y - ny) < 0.3 &&
        Math.abs(target.scale - ns) < 0.001

      if (converged) {
        zoomAnimRef.current = null
        return { x: target.x, y: target.y, scale: target.scale }
      }

      zoomAnimRef.current = requestAnimationFrame(animateZoom)
      return { x: nx, y: ny, scale: ns }
    })
  }, [])

  // Semantic zoom blend: 0 at scale ≤ 1.3, 1 at scale ≥ 2.2
  const zoomBlend = Math.max(0, Math.min(1, (transform.scale - 1.3) / 0.9))

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

  // Only render top edges by weight to reduce clutter
  const sortedEdges = useMemo(() => {
    const maxVisible = 120
    if (edges.length <= maxVisible) return edges
    return [...edges].sort((a, b) => (b.weight || 0) - (a.weight || 0)).slice(0, maxVisible)
  }, [edges])

  // Stable data key for simulation restart detection
  const dataKey = useMemo(() => {
    const nids = nodes.map(n => n.id).sort().join(',')
    const gnids = genreNodes.map(g => g.id).sort().join(',')
    const geids = genreEdges.map(e => `${e.source}-${e.target}`).sort().join(',')
    return `${nids}|${gnids}|${geids}`
  }, [nodes, genreNodes, genreEdges])
  const prevDataKeyRef = useRef(null)

  // KG-centric simulation: genres as anchors, artists as satellites
  useEffect(() => {
    if (animRef.current) cancelAnimationFrame(animRef.current)
    if (nodes.length === 0) return
    if (prevDataKeyRef.current === dataKey) return
    prevDataKeyRef.current = dataKey

    const cx = VB_W / 2
    const cy = VB_H / 2
    const hasGenres = genreNodes.length > 0
    const totalNodes = nodes.length + genreNodes.length

    // Pre-compute genre-artist mapping and genre-genre shared artist counts
    const genreToArtists = {} // genreNodeId -> Set of artist indices
    const artistGenreCount = {} // artist index -> number of genre edges
    for (const edge of genreEdges) {
      const si = nodeIndex[edge.source]
      const ti = nodeIndex[edge.target]
      if (si === undefined || ti === undefined) continue
      const genreIdx = si >= nodes.length ? si : ti >= nodes.length ? ti : -1
      const artistIdx = si < nodes.length ? si : ti < nodes.length ? ti : -1
      if (genreIdx >= 0 && artistIdx >= 0) {
        if (!genreToArtists[genreIdx]) genreToArtists[genreIdx] = new Set()
        genreToArtists[genreIdx].add(artistIdx)
        artistGenreCount[artistIdx] = (artistGenreCount[artistIdx] || 0) + 1
      }
    }

    // Genre-genre edges weighted by shared artists
    const genreGenreEdges = []
    const genreIndices = genreNodes.map((_, gi) => nodes.length + gi)
    for (let i = 0; i < genreIndices.length; i++) {
      for (let j = i + 1; j < genreIndices.length; j++) {
        const gi = genreIndices[i]
        const gj = genreIndices[j]
        const setI = genreToArtists[gi]
        const setJ = genreToArtists[gj]
        if (!setI || !setJ) continue
        let shared = 0
        for (const a of setI) { if (setJ.has(a)) shared++ }
        if (shared > 0) {
          genreGenreEdges.push({ i: gi, j: gj, weight: shared })
        }
      }
    }

    // Init: genres scattered (not ring), artists scattered broadly
    const initPos = [
      ...nodes.map(() => ({
        x: cx + (Math.random() - 0.5) * VB_W * 0.6,
        y: cy + (Math.random() - 0.5) * VB_H * 0.6,
      })),
      ...genreNodes.map(() => ({
        x: cx + (Math.random() - 0.5) * VB_W * 0.5,
        y: cy + (Math.random() - 0.5) * VB_H * 0.5,
      })),
    ]
    const initVel = Array.from({ length: totalNodes }, () => ({ x: 0, y: 0 }))

    posRef.current = initPos
    velRef.current = initVel
    setPositions([...initPos])

    let frameCount = 0
    const maxFrames = 250
    const damping = 0.65
    const artistRepulsion = 700
    const genreRepulsion = hasGenres ? 16000 : 800
    const genreArtistRepulsion = 1000
    const genreArtistAttraction = hasGenres ? 0.02 : 0.008
    const genreGenreAttraction = 0.008 // shared-artist-based
    const artistArtistAttraction = 0.003
    const centerForce = 0.01
    const genreMinDist = 110 // minimum px between genre node centers

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

          let rep
          if (isGenre(i) && isGenre(j)) rep = genreRepulsion
          else if (isGenre(i) || isGenre(j)) rep = genreArtistRepulsion
          else rep = artistRepulsion

          const force = rep / (dist * dist)
          const fx = (dx / dist) * force
          const fy = (dy / dist) * force
          forces[i].x += fx
          forces[i].y += fy
          forces[j].x -= fx
          forces[j].y -= fy
        }
      }

      // Genre-genre attraction: genres sharing artists pull together
      for (const ge of genreGenreEdges) {
        const dx = pos[ge.j].x - pos[ge.i].x
        const dy = pos[ge.j].y - pos[ge.i].y
        const dist = Math.sqrt(dx * dx + dy * dy) || 1
        // Stronger pull for more shared artists, but cap it
        const w = Math.min(ge.weight, 8)
        const force = dist * genreGenreAttraction * w
        const fx = (dx / dist) * force
        const fy = (dy / dist) * force
        forces[ge.i].x += fx
        forces[ge.i].y += fy
        forces[ge.j].x -= fx
        forces[ge.j].y -= fy
      }

      // Genre-genre minimum distance enforcement (anti-overlap)
      for (let i = 0; i < genreIndices.length; i++) {
        for (let j = i + 1; j < genreIndices.length; j++) {
          const gi = genreIndices[i]
          const gj = genreIndices[j]
          const dx = pos[gi].x - pos[gj].x
          const dy = pos[gi].y - pos[gj].y
          const dist = Math.sqrt(dx * dx + dy * dy) || 1
          if (dist < genreMinDist) {
            const push = (genreMinDist - dist) * 0.5
            const fx = (dx / dist) * push
            const fy = (dy / dist) * push
            forces[gi].x += fx
            forces[gi].y += fy
            forces[gj].x -= fx
            forces[gj].y -= fy
          }
        }
      }

      // Attraction: genre-artist edges — normalized by edge count
      // Artists with many genre connections get weaker pull per edge,
      // so they orbit their primary cluster instead of averaging to center
      for (const edge of genreEdges) {
        const si = nodeIndex[edge.source]
        const ti = nodeIndex[edge.target]
        if (si === undefined || ti === undefined) continue
        const dx = pos[ti].x - pos[si].x
        const dy = pos[ti].y - pos[si].y
        const dist = Math.sqrt(dx * dx + dy * dy) || 1
        // Normalize: artist with 1 genre = full pull, 3 genres = ~58% each
        const artistIdx = si < nodes.length ? si : ti < nodes.length ? ti : -1
        const edgeCount = artistIdx >= 0 ? (artistGenreCount[artistIdx] || 1) : 1
        const norm = 1 / Math.sqrt(edgeCount)
        const force = dist * genreArtistAttraction * norm
        const fx = (dx / dist) * force
        const fy = (dy / dist) * force
        forces[si].x += fx
        forces[si].y += fy
        forces[ti].x -= fx * 0.05
        forces[ti].y -= fy * 0.05
      }

      // Attraction: artist-artist edges (weak — secondary structure)
      for (const edge of edges) {
        const si = artistIndex[edge.source]
        const ti = artistIndex[edge.target]
        if (si === undefined || ti === undefined) continue
        const dx = pos[ti].x - pos[si].x
        const dy = pos[ti].y - pos[si].y
        const dist = Math.sqrt(dx * dx + dy * dy) || 1
        const force = dist * artistArtistAttraction
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
        pos[i].x = Math.max(40, Math.min(VB_W - 40, pos[i].x))
        pos[i].y = Math.max(40, Math.min(VB_H - 40, pos[i].y))
      }

      frameCount++
      if (frameCount % 2 === 0) {
        setPositions(pos.map(p => ({ ...p })))
      }

      animRef.current = requestAnimationFrame(simulate)
    }

    animRef.current = requestAnimationFrame(simulate)

    return () => {
      if (animRef.current) cancelAnimationFrame(animRef.current)
    }
  }, [dataKey, nodeIndex, artistIndex]) // eslint-disable-line react-hooks/exhaustive-deps

  // Zoom: wheel handler (smooth zoom toward cursor)
  const handleWheel = useCallback((e) => {
    e.preventDefault()
    const container = containerRef.current
    if (!container) return
    const rect = container.getBoundingClientRect()
    const mouseX = e.clientX - rect.left
    const mouseY = e.clientY - rect.top

    const scaleFactor = e.deltaY > 0 ? 0.93 : 1.07

    const prev = targetRef.current
    const newScale = Math.max(0.5, Math.min(4, prev.scale * scaleFactor))
    const svgX = (mouseX - prev.x) / prev.scale
    const svgY = (mouseY - prev.y) / prev.scale
    const newX = mouseX - svgX * newScale
    const newY = mouseY - svgY * newScale
    targetRef.current = { x: newX, y: newY, scale: newScale }

    if (!zoomAnimRef.current) {
      zoomAnimRef.current = requestAnimationFrame(animateZoom)
    }
  }, [animateZoom])

  // Pan: drag handlers (direct manipulation, no lerp)
  const handleMouseDown = useCallback((e) => {
    if (e.target.closest('.artist-node, circle[role="button"]')) return
    setIsDragging(true)
    const cur = targetRef.current
    dragStart.current = { x: e.clientX - cur.x, y: e.clientY - cur.y }
  }, [])

  const handleMouseMove = useCallback((e) => {
    if (!isDragging) return
    const newX = e.clientX - dragStart.current.x
    const newY = e.clientY - dragStart.current.y
    targetRef.current = { ...targetRef.current, x: newX, y: newY }
    setTransform(prev => ({ ...prev, x: newX, y: newY }))
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

  // Cleanup zoom animation on unmount
  useEffect(() => {
    return () => {
      if (zoomAnimRef.current) cancelAnimationFrame(zoomAnimRef.current)
    }
  }, [])

  const handleArtistMouseEnter = useCallback((node, pos) => {
    const clusterId = nodeClusterMap[node.id]
    const clusterLabel = clusterId != null ? (clusterNames[clusterId] || `Cerchia ${clusterId + 1}`) : null
    setTooltip({ ...node, x: pos.x, y: pos.y, clusterLabel })
  }, [nodeClusterMap, clusterNames])

  const handleGenreMouseEnter = useCallback((genreNode, pos) => {
    const clusterId = genreNode.cluster
    const cerchiaName = clusterId != null ? (clusterNames[clusterId] || null) : null
    setTooltip({
      ...genreNode,
      x: pos.x,
      y: pos.y,
      isGenreNode: true,
      cerchiaName,
    })
  }, [clusterNames])

  const handleMouseLeave = useCallback(() => {
    setTooltip(null)
  }, [])

  if (loading) {
    return (
      <div className="glow-card bg-surface rounded-xl p-5">
        <h3 className="text-text-primary font-display font-semibold mb-4">{title}</h3>
        <div className="aspect-[16/9] flex items-center justify-center">
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
      <div className="w-full">
        <div
          ref={containerRef}
          className="rounded-lg"
          style={{ overflow: 'hidden', cursor: isDragging ? 'grabbing' : 'grab' }}
          onMouseDown={handleMouseDown}
          onMouseMove={handleMouseMove}
          onMouseUp={handleMouseUp}
        >
          <svg
            ref={svgRef}
            viewBox={`0 0 ${VB_W} ${VB_H}`}
            className="w-full h-auto"
            preserveAspectRatio="xMidYMid meet"
            role="img"
            aria-label="Knowledge Graph artisti e generi"
          >
            <g transform={`translate(${transform.x}, ${transform.y}) scale(${transform.scale})`}>
              {/* Layer 1: Genre-artist edges — subtle KG connections */}
              {genreEdges.map((edge, i) => {
                const si = nodeIndex[edge.source]
                const ti = nodeIndex[edge.target]
                if (si === undefined || ti === undefined || !positions[si] || !positions[ti]) return null
                const opacity = 0.07 * (1 - zoomBlend * 0.5)
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
                    strokeWidth={0.4}
                  />
                )
              })}

              {/* Layer 2: Artist-artist edges — appear only when zoomed */}
              {sortedEdges.map((edge, i) => {
                const si = artistIndex[edge.source]
                const ti = artistIndex[edge.target]
                if (si === undefined || ti === undefined || !positions[si] || !positions[ti]) return null
                const baseOpacity = 0.05 + (edge.weight || 0) * 0.15
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

              {/* Layer 3: Artist nodes + labels — sized by play_count + connections */}
              {nodes.map((node, i) => {
                if (!positions[i]) return null
                const color = clusterColorMap[node.id] || '#6366f1'
                const conn = node.connections || 0
                const plays = node.play_count || 0
                const connNorm = Math.min(1, conn / 36)
                // play_count drives size: log scale for wide range, fallback to connections
                const playNorm = plays > 0 ? Math.min(1, Math.log(plays + 1) / Math.log(500)) : connNorm * 0.5
                const sizeWeight = Math.max(playNorm, connNorm * 0.4) // plays dominate, connections as floor

                // KG: small dots (3-8px), listened artists stand out
                const kgR = 3 + sizeWeight * 5
                // Rete: full size (6-22px)
                const reteR = 6 + sizeWeight * 16
                const r = kgR + (reteR - kgR) * zoomBlend

                // Opacity
                const kgOpacity = 0.45 + sizeWeight * 0.4
                const reteOpacity = 0.5 + sizeWeight * 0.45
                const fillOpacity = Math.min(0.95, kgOpacity + (reteOpacity - kgOpacity) * zoomBlend)

                const showGlow = sizeWeight > 0.7 && zoomBlend > 0.4
                const showStroke = sizeWeight > 0.5 && zoomBlend > 0.4

                // Label visibility: top artists always, mid on zoom
                const isTop = plays >= 30 || conn >= 28
                const isMid = plays >= 10 || conn >= 18
                let labelEl = null
                if (isTop) {
                  const labelOpacity = 0.7 + zoomBlend * 0.3
                  labelEl = (
                    <text
                      x={positions[i].x}
                      y={positions[i].y - r - 3}
                      textAnchor="middle"
                      fill="#ffffff"
                      fillOpacity={labelOpacity}
                      fontSize={11}
                      fontFamily="Inter, sans-serif"
                      fontWeight={600}
                      pointerEvents="none"
                    >
                      {node.name.length > 13 ? node.name.slice(0, 13) + '\u2026' : node.name}
                    </text>
                  )
                } else if (isMid && zoomBlend > 0.2) {
                  const labelOpacity = Math.min(1, (zoomBlend - 0.2) / 0.3)
                  labelEl = (
                    <text
                      x={positions[i].x}
                      y={positions[i].y - r - 3}
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
                }

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
                    {labelEl}
                  </g>
                )
              })}

              {/* Layer 4: Genre nodes — dominant KG hubs, fade on zoom */}
              {genreNodes.map((gn, gi) => {
                const posIdx = nodes.length + gi
                if (!positions[posIdx]) return null
                const clusterIdx = gn.cluster ?? 0
                const color = CLUSTER_COLORS[clusterIdx % CLUSTER_COLORS.length]
                const artistCount = gn.artist_count || 1
                const r = Math.max(28, Math.min(40, 24 + artistCount * 1.5))
                const pos = positions[posIdx]
                const genreOpacity = 1 - zoomBlend * 0.85

                return (
                  <g key={gn.id} opacity={genreOpacity}>
                    {/* Soft glow */}
                    <circle
                      cx={pos.x}
                      cy={pos.y}
                      r={r + 8}
                      fill={color}
                      fillOpacity={0.06}
                    />
                    {/* Main genre circle */}
                    <circle
                      cx={pos.x}
                      cy={pos.y}
                      r={r}
                      fill={color}
                      fillOpacity={0.15}
                      stroke={color}
                      strokeWidth={2.5}
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
                      y={pos.y + 1}
                      textAnchor="middle"
                      dominantBaseline="central"
                      fill="#ffffff"
                      fontSize={r > 32 ? 12 : 10}
                      fontFamily="Inter, sans-serif"
                      fontWeight={600}
                      pointerEvents="none"
                    >
                      {gn.name.length > 14 ? gn.name.slice(0, 14) + '\u2026' : gn.name}
                    </text>
                    {/* Artist count below label */}
                    <text
                      x={pos.x}
                      y={pos.y + (r > 32 ? 15 : 13)}
                      textAnchor="middle"
                      fill="#ffffff"
                      fillOpacity={0.5}
                      fontSize={8}
                      fontFamily="Inter, sans-serif"
                      pointerEvents="none"
                    >
                      {artistCount} artisti
                    </text>
                  </g>
                )
              })}

              {/* Artist labels rendered inside Layer 3 node groups */}
            </g>
          </svg>
        </div>
      </div>

      {/* Tooltip */}
      {tooltip && (
        <div
          className="absolute bg-surface-hover border border-border rounded-lg px-3 py-2 pointer-events-none z-10 shadow-lg min-w-[180px]"
          style={{
            left: `${(tooltip.x * transform.scale + transform.x) / (containerRef.current?.clientWidth || VB_W) * 100}%`,
            top: `${(tooltip.y * transform.scale + transform.y) / (containerRef.current?.clientHeight || VB_H) * 100 - 6}%`,
            transform: 'translate(-50%, -100%)',
          }}
        >
          {tooltip.isGenreNode ? (
            <>
              <p className="text-text-primary text-sm font-semibold">{tooltip.name}</p>
              <p className="text-accent text-xs font-medium">{tooltip.artist_count} artisti</p>
              {tooltip.cerchiaName && (
                <p className="text-text-secondary text-xs mt-0.5">Cerchia: {tooltip.cerchiaName}</p>
              )}
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
                {tooltip.play_count > 0 && <span>{tooltip.play_count} ascolti</span>}
                {tooltip.connections > 0 && <span>{tooltip.connections} conn.</span>}
                {tooltip.popularity > 0 && <span>Pop. {tooltip.popularity}</span>}
                {tooltip.followers > 0 && <span>{formatFollowers(tooltip.followers)} follower</span>}
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
