import { motion } from 'framer-motion'
import { StaggerContainer, StaggerItem } from '../../ui/StaggerContainer'

function ArtistGroup({ title, artists, highlight }) {
  if (!artists?.length) return null

  return (
    <div className="flex flex-col items-center">
      <h3 className="text-lg font-display font-semibold text-text-secondary mb-4">
        {title}
      </h3>
      <StaggerContainer className="flex gap-4">
        {artists.slice(0, 3).map((artist, i) => (
          <StaggerItem key={artist.name || i} className="flex flex-col items-center">
            <img
              src={artist.image || artist.image_url || artist.images?.[0]?.url}
              alt={artist.name}
              className={`w-20 h-20 rounded-full object-cover ${
                highlight ? 'ring-2 ring-accent' : ''
              }`}
            />
            <span className="text-sm text-text-primary mt-2 text-center max-w-[80px] truncate">
              {artist.name}
            </span>
          </StaggerItem>
        ))}
      </StaggerContainer>
    </div>
  )
}

export default function SlideArtistEvolution({ data }) {
  const evolution = data?.evolution
  const loyal = evolution?.artists?.loyal
  const rising = evolution?.artists?.rising

  if (!loyal?.length && !rising?.length) return null

  return (
    <div className="flex flex-col items-center justify-center min-h-[100dvh] px-6 py-16 relative">
      <motion.h2
        className="text-3xl font-display font-bold text-text-primary mb-10"
        initial={{ opacity: 0, y: -20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.4 }}
      >
        Il Tuo Universo Artistico
      </motion.h2>

      <div className="flex flex-col sm:flex-row gap-10">
        <ArtistGroup title="Fedelissimi" artists={loyal} highlight={false} />
        <ArtistGroup title="In Ascesa" artists={rising} highlight={true} />
      </div>
    </div>
  )
}
