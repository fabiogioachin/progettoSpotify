import { motion } from 'framer-motion'
import { Music } from 'lucide-react'
import { StaggerContainer, StaggerItem } from '../../ui/StaggerContainer'

export default function SlideTopTracks({ data }) {
  const tracks = data?.top_tracks?.slice(0, 5) || []
  const top = tracks[0]
  const rest = tracks.slice(1)

  if (!tracks.length) return null

  return (
    <div className="flex flex-col items-center justify-center min-h-[100dvh] px-6 py-16 relative">
      <motion.h2
        className="text-3xl font-display font-bold text-text-primary mb-8"
        initial={{ opacity: 0, y: -20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.4 }}
      >
        I Tuoi Brani Preferiti
      </motion.h2>

      {/* #1 Track — large display */}
      {top && (
        <motion.div
          className="flex flex-col items-center mb-8"
          initial={{ opacity: 0, scale: 0.9 }}
          animate={{ opacity: 1, scale: 1 }}
          transition={{ duration: 0.5, delay: 0.2 }}
        >
          {(top.album_image || top.album?.images?.[0]?.url || top.image_url) ? (
            <img
              src={top.album_image || top.album?.images?.[0]?.url || top.image_url}
              alt={top.name}
              className="w-40 h-40 rounded-lg object-cover shadow-lg mb-4"
              onError={(e) => {
                e.target.style.display = 'none'
                e.target.nextElementSibling.style.display = 'flex'
              }}
            />
          ) : null}
          <div
            className="w-40 h-40 rounded-lg bg-surface-hover items-center justify-center shadow-lg mb-4"
            style={{ display: (top.album_image || top.album?.images?.[0]?.url || top.image_url) ? 'none' : 'flex' }}
          >
            <Music size={40} className="text-text-muted" />
          </div>
          <span className="text-2xl font-display font-bold text-text-primary text-center">
            {top.name}
          </span>
          <span className="text-text-secondary">
            {top.artists?.[0]?.name || top.artist}
          </span>
        </motion.div>
      )}

      {/* Tracks 2-5 */}
      {rest.length > 0 && (
        <StaggerContainer className="w-full max-w-sm space-y-3">
          {rest.map((track, i) => (
            <StaggerItem key={track.id || i} className="flex items-center gap-3">
              <span className="text-text-muted font-display font-bold w-6 text-right">
                {i + 2}
              </span>
              {(track.album_image || track.album?.images?.[0]?.url || track.image_url) ? (
                <img
                  src={track.album_image || track.album?.images?.[0]?.url || track.image_url}
                  alt={track.name}
                  className="w-12 h-12 rounded object-cover flex-shrink-0"
                  onError={(e) => {
                    e.target.style.display = 'none'
                    e.target.nextElementSibling.style.display = 'flex'
                  }}
                />
              ) : null}
              <div
                className="w-12 h-12 rounded bg-surface-hover items-center justify-center flex-shrink-0"
                style={{ display: (track.album_image || track.album?.images?.[0]?.url || track.image_url) ? 'none' : 'flex' }}
              >
                <Music size={18} className="text-text-muted" />
              </div>
              <div className="min-w-0">
                <p className="text-text-primary text-sm font-medium truncate">
                  {track.name}
                </p>
                <p className="text-text-secondary text-xs truncate">
                  {track.artists?.[0]?.name || track.artist}
                </p>
              </div>
            </StaggerItem>
          ))}
        </StaggerContainer>
      )}
    </div>
  )
}
