import { useMemo } from 'react'

export default function OverlapHeatmap({ labels = [], matrix = [], title = 'Sovrapposizione Playlist', loading = false }) {

  const maxVal = useMemo(() => {
    let max = 0
    for (let i = 0; i < matrix.length; i++) {
      for (let j = 0; j < matrix[i].length; j++) {
        if (i !== j && matrix[i][j] > max) max = matrix[i][j]
      }
    }
    return max || 1
  }, [matrix])

  if (loading) {
    return (
      <div className="glow-card bg-surface rounded-xl p-5">
        <h3 className="text-text-primary font-display font-semibold mb-4">{title}</h3>
        <div className="h-48 flex items-center justify-center">
          <div className="w-8 h-8 border-2 border-accent border-t-transparent rounded-full animate-spin" />
        </div>
      </div>
    )
  }

  if (!labels.length || !matrix.length) {
    return null
  }

  // Limit to 10x10 max for readability
  const displayLabels = labels.slice(0, 10)
  const displayMatrix = matrix.slice(0, 10).map(row => row.slice(0, 10))

  return (
    <div className="glow-card bg-surface rounded-xl p-5">
      <h3 className="text-text-primary font-display font-semibold mb-4">{title}</h3>
      <div className="overflow-x-auto">
        <div className="min-w-[400px]">
          {/* Column headers */}
          <div className="flex ml-24">
            {displayLabels.map((label, i) => (
              <div key={i} className="flex-1 text-center px-0.5">
                <span className="text-text-muted text-[9px] block truncate -rotate-45 origin-bottom-left translate-x-4 w-16">
                  {label}
                </span>
              </div>
            ))}
          </div>
          <div className="mt-8">
            {displayMatrix.map((row, i) => (
              <div key={i} className="flex items-center gap-0.5 mb-0.5">
                <span className="text-text-secondary text-[10px] w-24 text-right pr-2 truncate flex-shrink-0">
                  {displayLabels[i]}
                </span>
                {row.map((value, j) => {
                  const isDiagonal = i === j
                  const opacity = isDiagonal ? 0.15 : Math.max(0.05, value / maxVal)
                  const bgColor = isDiagonal
                    ? 'rgba(255, 255, 255, 0.05)'
                    : `rgba(99, 102, 241, ${opacity})`
                  return (
                    <div
                      key={j}
                      className="flex-1 aspect-square flex items-center justify-center rounded-sm cursor-default transition-all duration-200 hover:scale-110"
                      style={{ backgroundColor: bgColor, minWidth: '28px', minHeight: '28px' }}
                      title={`${displayLabels[i]} × ${displayLabels[j]}: ${value}%`}
                    >
                      {!isDiagonal && value > 0 && (
                        <span className="text-[8px] text-white/80">{Math.round(value)}</span>
                      )}
                    </div>
                  )
                })}
              </div>
            ))}
          </div>
          {/* Legend */}
          <div className="flex items-center justify-end gap-2 mt-3">
            <span className="text-text-muted text-[10px]">0%</span>
            {[0.1, 0.3, 0.5, 0.7, 1].map((o, i) => (
              <div key={i} className="w-4 h-4 rounded-sm" style={{ backgroundColor: `rgba(99, 102, 241, ${o})` }} />
            ))}
            <span className="text-text-muted text-[10px]">100%</span>
          </div>
        </div>
      </div>
    </div>
  )
}
