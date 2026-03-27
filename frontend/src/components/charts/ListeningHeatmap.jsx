import { useMemo, useState } from 'react'
import { CalendarDays } from 'lucide-react'
import EmptyState from '../ui/EmptyState'

/**
 * Interpolates between color stops based on a normalized value [0, 1].
 * Stops: green (#1DB954) -> amber (#f59e0b) -> red (#ef4444) -> purple (#a855f7)
 */
function getColor(value, max) {
  if (max === 0 || value === 0) return 'rgba(255, 255, 255, 0.05)'

  const t = value / max // normalized 0..1

  const stops = [
    { pos: 0, r: 29, g: 185, b: 84 },    // #1DB954
    { pos: 0.33, r: 245, g: 158, b: 11 }, // #f59e0b
    { pos: 0.66, r: 239, g: 68, b: 68 },  // #ef4444
    { pos: 1, r: 168, g: 85, b: 247 },    // #a855f7
  ]

  let low = stops[0]
  let high = stops[stops.length - 1]
  for (let i = 0; i < stops.length - 1; i++) {
    if (t >= stops[i].pos && t <= stops[i + 1].pos) {
      low = stops[i]
      high = stops[i + 1]
      break
    }
  }

  const range = high.pos - low.pos
  const localT = range === 0 ? 0 : (t - low.pos) / range

  const r = Math.round(low.r + (high.r - low.r) * localT)
  const g = Math.round(low.g + (high.g - low.g) * localT)
  const b = Math.round(low.b + (high.b - low.b) * localT)

  // Minimum opacity of 0.6 for non-zero values so colors stay vibrant
  const opacity = 0.6 + 0.4 * t
  return `rgba(${r}, ${g}, ${b}, ${opacity})`
}

export default function ListeningHeatmap({ data = [], dayLabels = [], hourLabels = [], title = 'Mappa di Ascolto', loading = false }) {
  const [tooltip, setTooltip] = useState(null)

  const { maxCount, totalPlays, favDay, favHour } = useMemo(() => {
    if (!data.length) return { maxCount: 0, totalPlays: 0, favDay: '', favHour: '' }

    let max = 0
    let total = 0
    const dayTotals = new Array(data.length).fill(0)
    const hourTotals = new Array(24).fill(0)

    for (let day = 0; day < data.length; day++) {
      for (let hour = 0; hour < (data[day]?.length || 0); hour++) {
        const count = data[day][hour] || 0
        if (count > max) max = count
        total += count
        dayTotals[day] += count
        hourTotals[hour] += count
      }
    }

    const bestDayIdx = dayTotals.indexOf(Math.max(...dayTotals))
    const bestHourIdx = hourTotals.indexOf(Math.max(...hourTotals))

    return {
      maxCount: max,
      totalPlays: total,
      favDay: dayLabels[bestDayIdx] || '',
      favHour: bestHourIdx,
    }
  }, [data, dayLabels])

  if (loading) {
    return (
      <div className="glow-card bg-surface rounded-xl p-5">
        <div className="h-5 bg-surface-hover rounded w-48 mb-4 animate-pulse" />
        <div className="flex gap-2 mb-6 animate-pulse">
          <div className="h-16 bg-surface-hover rounded-lg flex-1" />
          <div className="h-16 bg-surface-hover rounded-lg flex-1" />
          <div className="h-16 bg-surface-hover rounded-lg flex-1" />
        </div>
        <div className="space-y-2 animate-pulse">
          {Array.from({ length: 7 }).map((_, i) => (
            <div key={i} className="flex gap-1">
              <div className="w-10 h-7 bg-surface-hover rounded" />
              {Array.from({ length: 12 }).map((_, j) => (
                <div key={j} className="w-7 h-7 bg-surface-hover rounded-lg flex-1" />
              ))}
            </div>
          ))}
        </div>
      </div>
    )
  }

  if (!data.length) {
    return (
      <div className="glow-card bg-surface rounded-xl p-5">
        <h3 className="text-text-primary font-display font-semibold text-lg mb-4">{title}</h3>
        <EmptyState icon={CalendarDays} message="Nessun dato di ascolto per questo periodo" />
      </div>
    )
  }

  return (
    <div className="glow-card bg-surface rounded-xl p-5">
      {/* Title */}
      <h3 className="text-text-primary font-display font-semibold text-lg mb-4">{title}</h3>

      {/* Storytelling header */}
      <div className="flex flex-wrap gap-3 mb-6">
        <div className="bg-surface-hover rounded-lg px-4 py-3 flex-1 min-w-[140px]">
          <p className="text-text-muted text-xs uppercase tracking-wide mb-1">Ascolti totali</p>
          <p className="text-text-primary font-display font-bold text-2xl">{totalPlays.toLocaleString('it-IT')}</p>
        </div>
        <div className="bg-surface-hover rounded-lg px-4 py-3 flex-1 min-w-[140px]">
          <p className="text-text-muted text-xs uppercase tracking-wide mb-1">Giorno preferito</p>
          <p className="text-text-primary font-display font-bold text-lg">{favDay}</p>
        </div>
        <div className="bg-surface-hover rounded-lg px-4 py-3 flex-1 min-w-[140px]">
          <p className="text-text-muted text-xs uppercase tracking-wide mb-1">Ora di punta</p>
          <p className="text-text-primary font-display font-bold text-lg">{String(favHour).padStart(2, '0')}:00</p>
        </div>
      </div>

      {/* Heatmap grid */}
      <div className="overflow-x-auto relative">
        <div className="min-w-[700px]">
          {/* Hour labels */}
          <div className="flex ml-12 mb-2 gap-1">
            {hourLabels.map((label, i) => (
              <div
                key={i}
                className="w-7 sm:w-8 text-center text-text-muted text-[10px] flex-shrink-0"
              >
                {i % 3 === 0 ? label : ''}
              </div>
            ))}
          </div>

          {/* Grid rows */}
          {data.map((row, dayIndex) => (
            <div
              key={dayIndex}
              className="heatmap-row flex items-center gap-1 mb-1"
              style={{ animationDelay: `${dayIndex * 80}ms` }}
            >
              <span className="text-text-secondary text-xs w-11 text-right flex-shrink-0 font-medium">
                {dayLabels[dayIndex] || ''}
              </span>
              <div className="flex gap-1">
                {row.map((count, hourIndex) => (
                  <div
                    key={hourIndex}
                    className="heatmap-cell w-7 h-7 sm:w-8 sm:h-8 rounded-lg cursor-default flex-shrink-0"
                    style={{
                      backgroundColor: getColor(count, maxCount),
                    }}
                    onMouseEnter={(e) => {
                      const rect = e.currentTarget.getBoundingClientRect()
                      setTooltip({
                        day: dayLabels[dayIndex],
                        hour: hourLabels[hourIndex],
                        count,
                        x: rect.left + rect.width / 2,
                        y: rect.top,
                      })
                    }}
                    onMouseLeave={() => setTooltip(null)}
                  />
                ))}
              </div>
            </div>
          ))}
        </div>

        {/* Tooltip */}
        {tooltip && (
          <div
            className="fixed pointer-events-none z-50 px-3 py-2 rounded-lg text-xs"
            style={{
              backgroundColor: '#181818',
              border: '1px solid #3e3e3e',
              left: tooltip.x,
              top: tooltip.y - 8,
              transform: 'translate(-50%, -100%)',
            }}
          >
            <p className="text-text-primary font-semibold">{tooltip.day} - {tooltip.hour}:00</p>
            <p className="text-text-secondary">
              {tooltip.count} {tooltip.count === 1 ? 'ascolto' : 'ascolti'}
            </p>
          </div>
        )}
      </div>

      {/* Color legend */}
      <div className="flex items-center justify-center gap-3 mt-5">
        <span className="text-text-muted text-xs">Pochi</span>
        <div
          className="h-3 w-48 rounded-full"
          style={{
            background: 'linear-gradient(to right, #1DB954, #f59e0b, #ef4444, #a855f7)',
          }}
        />
        <span className="text-text-muted text-xs">Molti</span>
      </div>
    </div>
  )
}
