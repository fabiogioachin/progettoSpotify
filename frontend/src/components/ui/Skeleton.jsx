/** Base skeleton with shimmer animation */
export function Skeleton({ className = '' }) {
  return (
    <div className={`animate-pulse bg-surface-hover rounded ${className}`} />
  )
}

/** Mimics KPICard shape: accent bar + title line + value line + icon circle */
export function SkeletonKPICard() {
  return (
    <div className="bg-surface rounded-xl p-5 relative overflow-hidden">
      {/* Accent bar */}
      <div className="absolute left-0 top-0 bottom-0 w-[3px] bg-surface-hover rounded-r-full" />
      <div className="flex items-start justify-between mb-3">
        <Skeleton className="h-4 w-24" />
        <Skeleton className="w-8 h-8 rounded-lg" />
      </div>
      <Skeleton className="h-8 w-20" />
    </div>
  )
}

/** Mimics TrackCard: circle/square + 2 text lines */
export function SkeletonTrackRow() {
  return (
    <div className="flex items-center gap-3 p-2">
      <Skeleton className="w-6 h-4" />
      <Skeleton className="w-10 h-10 rounded flex-shrink-0" />
      <div className="flex-1 space-y-2">
        <Skeleton className="h-4 w-3/4" />
        <Skeleton className="h-3 w-1/2" />
      </div>
    </div>
  )
}

/** Generic card skeleton with configurable height */
export function SkeletonCard({ height = 'h-64' }) {
  return (
    <div className={`bg-surface rounded-xl p-5 ${height}`}>
      <Skeleton className="h-5 w-40 mb-4" />
      <Skeleton className="h-full w-full rounded-lg" />
    </div>
  )
}

/** Renders N SkeletonCards in a grid */
export function SkeletonGrid({ count = 4, columns = 'grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4', cardHeight = 'h-24' }) {
  return (
    <div className={`grid ${columns} gap-4`}>
      {Array.from({ length: count }).map((_, i) => (
        <SkeletonCard key={i} height={cardHeight} />
      ))}
    </div>
  )
}
