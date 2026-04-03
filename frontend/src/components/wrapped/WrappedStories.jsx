import { useCallback, useEffect, useMemo, useState } from 'react'
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

export default function WrappedStories({
  data,
  availableSlides = [],
  isComputing = false,
  computePhase = '',
  computeProgress = { completed: 0, total: 5 },
  isWaiting = false,
  waitSeconds = 0,
  period,
  onPeriodChange,
  onClose,
}) {
  const [currentSlideId, setCurrentSlideId] = useState('intro')
  const [direction, setDirection] = useState(1)

  // Set of available slide IDs for quick lookup
  const availableSet = useMemo(() => new Set(availableSlides), [availableSlides])

  // Slides that are currently navigable
  const activeSlides = useMemo(
    () => ALL_SLIDES.filter((s) => availableSet.has(s.id)),
    [availableSet],
  )

  // Current index within activeSlides
  const currentIndex = useMemo(
    () => Math.max(0, activeSlides.findIndex((s) => s.id === currentSlideId)),
    [activeSlides, currentSlideId],
  )

  const goNext = useCallback(() => {
    if (currentIndex < activeSlides.length - 1) {
      setDirection(1)
      setCurrentSlideId(activeSlides[currentIndex + 1].id)
    }
  }, [currentIndex, activeSlides])

  const goPrev = useCallback(() => {
    if (currentIndex > 0) {
      setDirection(-1)
      setCurrentSlideId(activeSlides[currentIndex - 1].id)
    }
  }, [currentIndex, activeSlides])

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
      {/* Progress bars — all expected slides as segments */}
      <div className="absolute top-0 left-0 right-0 z-50 flex gap-1 px-3 pt-3">
        {ALL_SLIDES.map((slide) => {
          const isAvailable = availableSet.has(slide.id)
          const activeIdx = activeSlides.findIndex((s) => s.id === slide.id)
          const isVisited = isAvailable && activeIdx <= currentIndex

          return (
            <div
              key={slide.id}
              className="flex-1 h-[3px] bg-white/20 rounded-full overflow-hidden"
            >
              {isAvailable ? (
                <div
                  className={`h-full rounded-full transition-all duration-300 ${
                    isVisited ? 'bg-accent w-full' : 'w-0'
                  }`}
                />
              ) : (
                /* Shimmer for pending slides */
                <div
                  className="h-full w-full rounded-full bg-gradient-to-r from-white/5 via-white/15 to-white/5 animate-shimmer"
                  style={{ backgroundSize: '200% 100%' }}
                />
              )}
            </div>
          )
        })}
      </div>

      {/* Close button */}
      <button
        onClick={onClose}
        className="absolute top-4 right-4 z-50 p-2 rounded-full text-text-secondary hover:text-text-primary hover:bg-surface-hover transition-colors"
        aria-label="Chiudi"
      >
        <X size={20} />
      </button>

      {/* Computing indicator */}
      {isComputing && (
        <div className="absolute top-4 left-4 z-50 flex items-center gap-2 text-text-muted text-xs">
          <div className="w-2 h-2 bg-accent rounded-full animate-pulse" />
          <span>
            {isWaiting
              ? `In attesa (${waitSeconds}s)...`
              : computePhase
                ? `${computePhase} (${computeProgress.completed}/${computeProgress.total})`
                : `Elaborazione in corso (${computeProgress.completed}/${computeProgress.total})...`}
          </span>
        </div>
      )}

      {/* Slide content */}
      <AnimatePresence mode="wait" custom={direction}>
        <motion.div
          key={currentSlideId}
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

      {/* Period selector */}
      {onPeriodChange && (
        <div className="absolute bottom-6 left-0 right-0 z-50 flex justify-center pointer-events-auto">
          <PeriodSelector value={period} onChange={onPeriodChange} />
        </div>
      )}

      {/* Click zones */}
      <div
        className="absolute inset-0 z-10"
        onPointerDown={handlePointerDown}
      />
    </div>
  )
}
