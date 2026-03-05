import { useState } from 'react'
import { Info } from 'lucide-react'

export default function InfoTip({ text }) {
  const [show, setShow] = useState(false)
  return (
    <span
      className="relative inline-flex items-center ml-1.5"
      onMouseEnter={() => setShow(true)}
      onMouseLeave={() => setShow(false)}
    >
      <Info size={14} className="text-text-muted hover:text-accent transition-colors cursor-help" />
      {show && (
        <span className="absolute bottom-full left-1/2 -translate-x-1/2 mb-2 px-3 py-1.5 text-xs text-text-secondary bg-surface-hover border border-border rounded-lg shadow-lg whitespace-nowrap z-20">
          {text}
        </span>
      )}
    </span>
  )
}
