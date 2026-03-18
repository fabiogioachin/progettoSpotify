import { motion } from 'framer-motion'

export default function SlideArtistNetwork({ data }) {
  const network = data?.network
  if (!network) return null

  const metrics = network.metrics
  const clusterCount = metrics?.cluster_count || 0
  const clusterNames = network.cluster_names
    ? (Array.isArray(network.cluster_names)
        ? network.cluster_names
        : Object.values(network.cluster_names))
    : []
  const topGenres = network.top_genres?.slice(0, 3) || []

  return (
    <div className="flex flex-col items-center justify-center min-h-[100dvh] px-6 py-16 relative">
      <motion.h2
        className="text-3xl font-display font-bold text-text-primary mb-10"
        initial={{ opacity: 0, y: -20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.4 }}
      >
        Le Tue Cerchie
      </motion.h2>

      <motion.span
        className="text-6xl font-display font-bold text-accent mb-2"
        initial={{ opacity: 0, scale: 0.8 }}
        animate={{ opacity: 1, scale: 1 }}
        transition={{ duration: 0.5, delay: 0.2 }}
      >
        {clusterCount}
      </motion.span>

      <motion.p
        className="text-text-secondary mb-8"
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ delay: 0.4 }}
      >
        Cerchie musicali
      </motion.p>

      {/* Cluster name pills */}
      {clusterNames.length > 0 && (
        <motion.div
          className="flex flex-wrap justify-center gap-2 mb-6 max-w-md"
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.5 }}
        >
          {clusterNames.map((name) => (
            <span
              key={name}
              className="px-3 py-1 rounded-full bg-surface text-sm text-text-primary border border-border"
            >
              {name}
            </span>
          ))}
        </motion.div>
      )}

      {/* Top genres */}
      {topGenres.length > 0 && (
        <motion.div
          className="flex flex-wrap justify-center gap-2"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ delay: 0.7 }}
        >
          {topGenres.map((genre) => (
            <span
              key={genre}
              className="px-2.5 py-0.5 rounded-full bg-accent/10 text-xs text-accent border border-accent/20"
            >
              {genre}
            </span>
          ))}
        </motion.div>
      )}
    </div>
  )
}
