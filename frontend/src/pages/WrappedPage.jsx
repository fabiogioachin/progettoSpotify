import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useWrappedTask } from '../hooks/useWrappedTask'
import WrappedStories from '../components/wrapped/WrappedStories'

export default function WrappedPage() {
  const navigate = useNavigate()
  const [period, setPeriod] = useState('medium_term')

  const {
    data,
    availableSlides,
    isLoading,
    isWaiting,
    waitSeconds,
    phase,
    completedServices,
    totalServices,
    error,
  } = useWrappedTask(period)

  if (error) {
    return (
      <div className="min-h-[100dvh] bg-background flex flex-col items-center justify-center gap-4">
        <p className="text-text-secondary">{error}</p>
        <button
          onClick={() => navigate('/dashboard')}
          className="px-5 py-2.5 bg-accent hover:bg-accent-hover text-white rounded-lg font-medium text-sm transition-colors"
        >
          Torna alla Dashboard
        </button>
      </div>
    )
  }

  // Show WrappedStories immediately — intro slide is always available
  return (
    <WrappedStories
      data={data || {}}
      availableSlides={availableSlides}
      isComputing={isLoading}
      computePhase={phase}
      computeProgress={{ completed: completedServices, total: totalServices }}
      isWaiting={isWaiting}
      waitSeconds={waitSeconds}
      period={period}
      onPeriodChange={setPeriod}
      onClose={() => navigate('/dashboard')}
    />
  )
}
