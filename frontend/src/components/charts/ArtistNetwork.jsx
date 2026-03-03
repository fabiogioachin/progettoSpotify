import { useRef, useEffect, useState, useCallback, useMemo } from 'react'

const CLUSTER_COLORS = [
  '#6366f1', '#1DB954', '#f59e0b', '#ec4899', '#06b6d4',
  '#8b5cf6', '#ef4444', '#10b981', '#f97316', '#14b8a6',
]

export default function ArtistNetwork({ nodes = [], edges = [], clusters = [], title = 'Ecosistema Artisti', loading = false }) {
  const svgRef = useRef(null)
  const animRef = useRef(null)
  const [tooltip, setTooltip] = useState(null)
  const [positions, setPositions] = useState([])
  const posRef = useRef([])
  const velRef = useRef([])

  // Build cluster color map
  const clusterColorMap = useMemo(() => {
    const map = {}
    clusters.forEach(c => {
      map[c.id] = CLUSTER_COLORS[c.cluster % CLUSTER_COLORS.length]
    })
    return map
  }, [clusters])

  // Build node index map
  const nodeIndex = useMemo(() => {
    const map = {}
    nodes.forEach((n, i) => { map[n.id] = i })
    return map
  }, [nodes])

  // Initialize positions
  useEffect(() => {
    if (nodes.length === 0) return

    const width = 700
    const height = 500
    const cx = width / 2
    const cy = height / 2

    const initPos = nodes.map((_, i) => ({
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

      // Reset forces
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
        // Bounds
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
  }, [nodes, edges, nodeIndex])

  const handleMouseEnter = useCallback((node, pos) => {
    setTooltip({ name: node.name, x: pos.x, y: pos.y, isTop: node.is_top })
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
    return (
      <div className="glow-card bg-surface rounded-xl p-5">
        <h3 className="text-text-primary font-display font-semibold mb-4">{title}</h3>
        <p className="text-text-muted text-sm text-center py-8">Nessun dato disponibile</p>
      </div>
    )
  }

  return (
    <div className="glow-card bg-surface rounded-xl p-5 relative">
      <h3 className="text-text-primary font-display font-semibold mb-4">{title}</h3>
      <svg ref={svgRef} viewBox="0 0 700 500" className="w-full h-auto" style={{ maxHeight: '500px' }}>
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
              strokeOpacity={0.06}
              strokeWidth={1}
            />
          )
        })}
        {/* Nodes */}
        {nodes.map((node, i) => {
          if (!positions[i]) return null
          const color = clusterColorMap[node.id] || '#6366f1'
          const r = node.is_top ? 10 : 5
          return (
            <circle
              key={node.id}
              cx={positions[i].x}
              cy={positions[i].y}
              r={r}
              fill={color}
              fillOpacity={node.is_top ? 0.9 : 0.5}
              stroke={node.is_top ? '#ffffff' : 'none'}
              strokeWidth={node.is_top ? 1.5 : 0}
              className="cursor-pointer transition-all duration-200"
              onMouseEnter={() => handleMouseEnter(node, positions[i])}
              onMouseLeave={handleMouseLeave}
            />
          )
        })}
        {/* Node labels for top artists */}
        {nodes.map((node, i) => {
          if (!node.is_top || !positions[i]) return null
          return (
            <text
              key={`label-${node.id}`}
              x={positions[i].x}
              y={positions[i].y - 14}
              textAnchor="middle"
              fill="#b3b3b3"
              fontSize={9}
              fontFamily="Inter, sans-serif"
            >
              {node.name.length > 15 ? node.name.slice(0, 15) + '\u2026' : node.name}
            </text>
          )
        })}
      </svg>
      {/* Tooltip */}
      {tooltip && (
        <div
          className="absolute bg-surface-hover border border-border rounded-lg px-3 py-2 pointer-events-none z-10 shadow-lg"
          style={{ left: `${(tooltip.x / 700) * 100}%`, top: `${(tooltip.y / 500) * 100 - 8}%`, transform: 'translate(-50%, -100%)' }}
        >
          <p className="text-text-primary text-sm font-medium">{tooltip.name}</p>
          {tooltip.isTop && <p className="text-accent text-xs">Top Artist</p>}
        </div>
      )}
      {/* Cluster Legend */}
      <div className="flex flex-wrap gap-3 mt-3">
        {[...new Set(clusters.map(c => c.cluster))].slice(0, 8).map(clusterId => (
          <div key={clusterId} className="flex items-center gap-1.5">
            <div className="w-3 h-3 rounded-full" style={{ backgroundColor: CLUSTER_COLORS[clusterId % CLUSTER_COLORS.length] }} />
            <span className="text-text-muted text-xs">Cluster {clusterId + 1}</span>
          </div>
        ))}
      </div>
    </div>
  )
}
