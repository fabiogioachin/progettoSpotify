import { useCallback, useEffect, useState } from 'react'
import { AnimatePresence, motion } from 'framer-motion'
import { X } from 'lucide-react'
import PeriodSelector from '../ui/PeriodSelector'

import SlideIntro from './slides/SlideIntro'
import SlideTopTracks from './slides/SlideTopTracks'
import SlideListeningHabits from './slides/SlideListeningHabits'
import SlidePeakHours from './slides/SlidePeakHours'
import SlideArtistEvolution from './slides/SlideArtistEvolution'
import SlideTopGenres from './slides/SlideTopGenres'
import SlideArtistNetwork from './slides/SlideArtistNetwork'
import SlideOutro from './slides/SlideOutro'

const ALL_SLIDES = [
  { id: 'intro', component: SlideIntro },
  { id: 'top_tracks', component: SlideTopTracks },
  { id: 'listening_habits', component: SlideListeningHabits },
  { id: 'peak_hours', component: SlidePeakHours },
  { id: 'artist_evolution', component: SlideArtistEvolution },
  { id: 'top_genres', component: SlideTopGenres },
  { id: 'artist_network', component: SlideArtistNetwork },
  { id: 'outro', component: SlideOutro },
]

const slideVariants = {
  enter: (direction) => ({ opacity: 0, x: direction > 0 ? 60 : -60 }),
  center: { opacity: 1, x: 0, transition: { duration: 0.35, ease: 'easeOut' } },
  exit: (direction) => ({
    opacity: 0,
    x: direction > 0 ? -60 : 60,
    transition: { duration: 0.2 },
  }),
}

export default function WrappedStories({ data, period, onPeriodChange, onClose }) {
  const [currentIndex, setCurrentIndex] = useState(0)
  const [direction, setDirection] = useState(1)

  const slides = ALL_SLIDES.filter((s) =>
    data?.available_slides?.includes(s.id)
  )

  // Fallback: if available_slides is missing, show all slides
  const activeSlides = slides.length > 0 ? slides : ALL_SLIDES

  const goNext = useCallback(() => {
    if (currentIndex < activeSlides.length - 1) {
      setDirection(1)
      setCurrentIndex((i) => i + 1)
    }
  }, [currentIndex, activeSlides.length])

  const goPrev = useCallback(() => {
    if (currentIndex > 0) {
      setDirection(-1)
      setCurrentIndex((i) => i - 1)
    }
  }, [currentIndex])

  // Keyboard navigation
  useEffect(() => {
    const handleKey = (e) => {
      if (e.key === 'ArrowRight') goNext()
      else if (e.key === 'ArrowLeft') goPrev()
      else if (e.key === 'Escape') onClose()
    }
    window.addEventListener('keydown', handleKey)
    return () => window.removeEventListener('keydown', handleKey)
  }, [goNext, goPrev, onClose])

  const handlePointerDown = (e) => {
    const rect = e.currentTarget.getBoundingClientRect()
    const x = e.clientX - rect.left
    const third = rect.width / 3

    if (x < third) {
      goPrev()
    } else {
      goNext()
    }
  }

  const CurrentSlide = activeSlides[currentIndex]?.component
  if (!CurrentSlide) return null

  return (
    <div className="fixed inset-0 bg-background z-[100]">
      {/* Progress bars */}
      <div className="absolute top-0 left-0 right-0 z-50 flex gap-1 px-3 pt-3">
        {activeSlides.map((_, i) => (
          <div
            key={i}
            className="flex-1 h-[3px] bg-white/20 rounded-full overflow-hidden"
          >
            <div
              className={`h-full rounded-full transition-all duration-300 ${
                i <= currentIndex ? 'bg-accent w-full' : 'w-0'
              }`}
            />
          </div>
        ))}
      </div>

      {/* Close button */}
      <button
        onClick={onClose}
        className="absolute top-4 right-4 z-50 p-2 rounded-full text-text-secondary hover:text-text-primary hover:bg-surface-hover transition-colors"
        aria-label="Chiudi"
      >
        <X size={20} />
      </button>

      {/* Slide content — pointer-events-none so click zone works through it */}
      <AnimatePresence mode="wait" custom={direction}>
        <motion.div
          key={currentIndex}
          custom={direction}
          variants={slideVariants}
          initial="enter"
          animate="center"
          exit="exit"
          className="absolute inset-0 z-20 pointer-events-none"
        >
          <CurrentSlide data={data} />
        </motion.div>
      </AnimatePresence>

      {/* Period selector — bottom center, interactive */}
      {onPeriodChange && (
        <div className="absolute bottom-6 left-0 right-0 z-50 flex justify-center pointer-events-auto">
          <PeriodSelector value={period} onChange={onPeriodChange} />
        </div>
      )}

      {/* Click zones — below slide content, handles navigation taps */}
      <div
        className="absolute inset-0 z-10"
        onPointerDown={handlePointerDown}
      />
    </div>
  )
}
