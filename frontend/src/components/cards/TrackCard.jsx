export default function TrackCard({ track, index }) {
  const energy = track.features?.energy ?? 0
  const valence = track.features?.valence ?? 0

  return (
    <div className="flex items-center gap-3 p-3 rounded-lg hover:bg-surface-hover transition-all duration-300 group">
      {/* Posizione */}
      <span className="text-text-muted text-sm w-6 text-right font-mono">
        {index + 1}
      </span>

      {/* Album art */}
      {track.album_image ? (
        <img
          src={track.album_image}
          alt={track.album}
          className="w-10 h-10 rounded-md object-cover"
        />
      ) : (
        <div className="w-10 h-10 rounded-md bg-surface-hover flex items-center justify-center">
          <span className="text-text-muted text-xs">♪</span>
        </div>
      )}

      {/* Info */}
      <div className="flex-1 min-w-0">
        <p className="text-text-primary text-sm font-medium truncate">
          {track.name}
        </p>
        <p className="text-text-muted text-xs truncate">
          {track.artist}
        </p>
      </div>

      {/* Mini barre energia/valence */}
      <div className="flex items-center gap-2">
        <MiniBar label="E" value={energy} color="#f59e0b" />
        <MiniBar label="V" value={valence} color="#10b981" />
      </div>
    </div>
  )
}

function MiniBar({ label, value, color }) {
  return (
    <div className="flex items-center gap-1">
      <span className="text-[10px] text-text-muted w-3">{label}</span>
      <div className="w-12 h-1.5 bg-border rounded-full overflow-hidden">
        <div
          className="h-full rounded-full transition-all duration-700"
          style={{
            width: `${value * 100}%`,
            backgroundColor: color,
          }}
        />
      </div>
    </div>
  )
}
