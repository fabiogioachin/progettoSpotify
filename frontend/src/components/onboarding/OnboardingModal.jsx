import { useState, useCallback } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { Music, BarChart3, Sparkles, Clock, TrendingUp, RefreshCw, X } from 'lucide-react'
import api from '../../lib/api'

const steps = [
  {
    id: 'welcome',
    title: 'Benvenuto su Wrap!',
    description:
      'La tua dashboard personale per scoprire pattern nascosti nei tuoi ascolti musicali.',
    icons: [Music, BarChart3, Sparkles],
  },
  {
    id: 'how-it-works',
    title: 'Come funziona',
    items: [
      {
        icon: Clock,
        text: 'I tuoi ascolti vengono raccolti automaticamente ogni ora',
      },
      {
        icon: TrendingUp,
        text: 'Analisi avanzate rivelano i tuoi pattern e le tue tendenze',
      },
      {
        icon: RefreshCw,
        text: 'I dati si arricchiscono nel tempo \u2014 pi\u00f9 ascolti, pi\u00f9 insights',
      },
    ],
  },
  {
    id: 'ready',
    title: 'Quasi pronto!',
    description:
      'I tuoi dati arriveranno nelle prossime ore. Nel frattempo, esplora la dashboard \u2014 vedrai i primi risultati appena disponibili.',
  },
]

const slideVariants = {
  enter: (direction) => ({
    x: direction > 0 ? 80 : -80,
    opacity: 0,
  }),
  center: {
    x: 0,
    opacity: 1,
  },
  exit: (direction) => ({
    x: direction > 0 ? -80 : 80,
    opacity: 0,
  }),
}

export default function OnboardingModal({ onClose }) {
  const [step, setStep] = useState(0)
  const [direction, setDirection] = useState(1)
  const [dontShowAgain, setDontShowAgain] = useState(false)

  const handleComplete = useCallback(async () => {
    if (dontShowAgain) {
      localStorage.setItem('wrap_onboarding_dismissed', 'true')
    }
    try {
      await api.post('/auth/onboarding-complete')
    } catch (err) {
      console.warn('Onboarding complete failed:', err)
    }
    onClose()
  }, [onClose, dontShowAgain])

  const handleNext = () => {
    if (step < steps.length - 1) {
      setDirection(1)
      setStep((s) => s + 1)
    } else {
      handleComplete()
    }
  }

  const current = steps[step]
  const isLast = step === steps.length - 1

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm">
      <motion.div
        initial={{ opacity: 0, scale: 0.95 }}
        animate={{ opacity: 1, scale: 1 }}
        exit={{ opacity: 0, scale: 0.95 }}
        transition={{ duration: 0.25 }}
        className="bg-surface rounded-2xl p-8 max-w-md w-full mx-4 shadow-2xl relative"
      >
        {/* Close button */}
        <button
          onClick={handleComplete}
          className="absolute top-4 right-4 text-text-muted hover:text-text-primary transition-colors"
          aria-label="Chiudi"
        >
          <X size={20} />
        </button>

        {/* Step content with slide animation */}
        <div className="min-h-[240px] flex flex-col justify-center">
          <AnimatePresence mode="wait" custom={direction}>
            <motion.div
              key={current.id}
              custom={direction}
              variants={slideVariants}
              initial="enter"
              animate="center"
              exit="exit"
              transition={{ duration: 0.25, ease: 'easeInOut' }}
            >
              {/* Step 1: Welcome */}
              {current.id === 'welcome' && (
                <div className="text-center">
                  <div className="flex justify-center gap-3 mb-6">
                    {current.icons.map((Icon, i) => (
                      <div
                        key={i}
                        className="w-12 h-12 rounded-xl bg-accent/15 flex items-center justify-center"
                      >
                        <Icon size={24} className="text-accent" />
                      </div>
                    ))}
                  </div>
                  <h2 className="text-xl font-display font-bold text-text-primary mb-3">
                    {current.title}
                  </h2>
                  <p className="text-text-secondary text-sm leading-relaxed">
                    {current.description}
                  </p>
                </div>
              )}

              {/* Step 2: How it works */}
              {current.id === 'how-it-works' && (
                <div>
                  <h2 className="text-xl font-display font-bold text-text-primary mb-5 text-center">
                    {current.title}
                  </h2>
                  <div className="space-y-4">
                    {current.items.map((item, i) => {
                      const Icon = item.icon
                      return (
                        <div key={i} className="flex items-start gap-3">
                          <div className="w-9 h-9 rounded-lg bg-accent/15 flex items-center justify-center shrink-0 mt-0.5">
                            <Icon size={18} className="text-accent" />
                          </div>
                          <p className="text-text-secondary text-sm leading-relaxed pt-1.5">
                            {item.text}
                          </p>
                        </div>
                      )
                    })}
                  </div>
                </div>
              )}

              {/* Step 3: Ready */}
              {current.id === 'ready' && (
                <div className="text-center">
                  <div className="w-14 h-14 rounded-2xl bg-accent/15 flex items-center justify-center mx-auto mb-5">
                    <Sparkles size={28} className="text-accent" />
                  </div>
                  <h2 className="text-xl font-display font-bold text-text-primary mb-3">
                    {current.title}
                  </h2>
                  <p className="text-text-secondary text-sm leading-relaxed">
                    {current.description}
                  </p>
                </div>
              )}
            </motion.div>
          </AnimatePresence>
        </div>

        {/* Progress dots */}
        <div className="flex justify-center gap-2 mt-6 mb-5">
          {steps.map((_, i) => (
            <div
              key={i}
              className={`w-2 h-2 rounded-full transition-colors duration-200 ${
                i === step ? 'bg-accent' : 'bg-surface-hover'
              }`}
            />
          ))}
        </div>

        {/* Don't show again checkbox */}
        <label className="flex items-center gap-2 mb-4 cursor-pointer select-none group">
          <input
            type="checkbox"
            checked={dontShowAgain}
            onChange={(e) => setDontShowAgain(e.target.checked)}
            className="w-4 h-4 rounded border-surface-hover text-accent focus:ring-accent/30 focus:ring-2 bg-surface-hover cursor-pointer"
          />
          <span className="text-text-muted text-xs group-hover:text-text-secondary transition-colors">
            Non mostrare più
          </span>
        </label>

        {/* Action button */}
        <button
          onClick={handleNext}
          className="w-full py-2.5 rounded-xl bg-accent hover:bg-accent-hover text-white font-display font-semibold text-sm transition-colors"
        >
          {isLast ? 'Inizia' : 'Avanti'}
        </button>
      </motion.div>
    </div>
  )
}
