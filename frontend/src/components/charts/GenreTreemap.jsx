import { ResponsiveContainer, Treemap, Tooltip } from 'recharts'
import { TOOLTIP_STYLE } from '../../lib/chartTheme'

const GENRE_COLORS = [
  '#6366f1', '#818cf8', '#a5b4fc',
  '#10b981', '#34d399', '#6ee7b7',
  '#f59e0b', '#fbbf24', '#fcd34d',
  '#ec4899', '#f472b6', '#f9a8d4',
  '#06b6d4', '#22d3ee', '#67e8f9',
]

export default function GenreTreemap({ genres, title = 'Distribuzione Generi', loading = false }) {
  if (loading) {
    return (
      <div className="glow-card bg-surface rounded-xl p-5 animate-pulse">
        <div className="h-5 bg-surface-hover rounded w-32 mb-4" />
        <div className="h-[300px] bg-surface-hover rounded" />
      </div>
    )
  }

  if (!genres || Object.keys(genres).length === 0) {
    return <EmptyState />
  }

  const data = Object.entries(genres)
    .slice(0, 12)
    .map(([name, value], idx) => ({
      name: `${name} (${value}%)`,
      size: value,
      fill: GENRE_COLORS[idx % GENRE_COLORS.length],
    }))

  return (
    <div className="glow-card bg-surface rounded-xl p-5">
      <h3 className="text-text-primary font-display font-semibold mb-4">{title}</h3>
      <ResponsiveContainer width="100%" height={300}>
        <Treemap
          data={data}
          dataKey="size"
          nameKey="name"
          stroke="#121212"
          animationDuration={1200}
          content={<CustomTreemapContent />}
        >
          <Tooltip
            {...TOOLTIP_STYLE}
            formatter={(val) => [`${val}%`, 'Percentuale']}
          />
        </Treemap>
      </ResponsiveContainer>
    </div>
  )
}

function CustomTreemapContent({ x, y, width, height, name, fill }) {
  if (width < 40 || height < 30) return null

  return (
    <g>
      <rect
        x={x}
        y={y}
        width={width}
        height={height}
        fill={fill}
        stroke="#121212"
        strokeWidth={2}
        rx={4}
        style={{ opacity: 0.85 }}
      />
      {width > 60 && height > 35 && (
        <text
          x={x + width / 2}
          y={y + height / 2}
          fill="#fff"
          textAnchor="middle"
          dominantBaseline="middle"
          fontSize={Math.min(12, width / 8)}
          fontWeight="500"
        >
          {name}
        </text>
      )}
    </g>
  )
}

function EmptyState() {
  return (
    <div className="glow-card bg-surface rounded-xl p-5 flex items-center justify-center h-[380px]">
      <p className="text-text-muted text-sm">Nessun dato generi disponibile</p>
    </div>
  )
}
