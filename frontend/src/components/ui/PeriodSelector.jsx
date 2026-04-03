import { TIME_PERIODS } from '../../lib/constants'

export default function PeriodSelector({ value, onChange, options }) {
  const periods = options || TIME_PERIODS
  return (
    <div className="flex gap-1 bg-surface rounded-lg p-1" role="group" aria-label="Seleziona periodo">
      {periods.map((period) => (
        <button
          key={period.value}
          onClick={() => onChange(period.value)}
          aria-pressed={value === period.value}
          className={`px-3 py-1.5 rounded-md text-sm font-medium transition-all duration-300
            ${value === period.value
              ? 'bg-accent text-white shadow-lg shadow-accent/20'
              : 'text-text-secondary hover:text-text-primary hover:bg-surface-hover'
            }`}
        >
          {period.label}
        </button>
      ))}
    </div>
  )
}
