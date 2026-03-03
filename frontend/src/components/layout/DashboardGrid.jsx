export default function DashboardGrid({ children }) {
  return (
    <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-4">
      {children}
    </div>
  )
}

export function FullWidthSection({ children, className = '' }) {
  return (
    <div className={`col-span-full ${className}`}>
      {children}
    </div>
  )
}

export function HalfSection({ children, className = '' }) {
  return (
    <div className={`col-span-full md:col-span-1 xl:col-span-2 ${className}`}>
      {children}
    </div>
  )
}
