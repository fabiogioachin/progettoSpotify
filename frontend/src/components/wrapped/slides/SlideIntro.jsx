import { motion } from 'framer-motion'
import { useAuth } from '../../../contexts/AuthContext'

export default function SlideIntro() {
  const { user } = useAuth()

  return (
    <div className="flex flex-col items-center justify-center min-h-[100dvh] px-6 py-16 relative overflow-hidden">
      {/* Pulsing rings */}
      {[1, 2, 3].map((i) => (
        <motion.div
          key={i}
          className="absolute rounded-full border border-accent/20"
          style={{ width: 200 + i * 100, height: 200 + i * 100 }}
          animate={{ scale: [1, 1.1, 1], opacity: [0.1, 0.2, 0.1] }}
          transition={{ duration: 3, repeat: Infinity, delay: i * 0.5 }}
        />
      ))}

      <motion.h1
        className="gradient-text text-5xl sm:text-6xl font-display font-bold mb-4 relative z-10"
        initial={{ opacity: 0, scale: 0.9 }}
        animate={{ opacity: 1, scale: 1 }}
        transition={{ duration: 0.6, ease: 'easeOut' }}
      >
        Il Tuo Wrapped
      </motion.h1>

      <motion.p
        className="text-xl text-text-primary font-display relative z-10"
        initial={{ opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.4, delay: 0.3 }}
      >
        {user?.display_name}
      </motion.p>

      <motion.p
        className="text-text-secondary mt-2 relative z-10"
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ duration: 0.4, delay: 0.6 }}
      >
        Scopri le tue abitudini musicali
      </motion.p>
    </div>
  )
}
