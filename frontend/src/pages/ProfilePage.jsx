import { useState, useEffect, useRef } from 'react'
import { Share2, Clock, Flame } from 'lucide-react'
import { AnimatePresence } from 'framer-motion'
import { useSpotifyData } from '../hooks/useSpotifyData'
import { SkeletonKPICard, SkeletonCard } from '../components/ui/Skeleton'
import { StaggerContainer, StaggerItem } from '../components/ui/StaggerContainer'
import ObscurityGauge from '../components/profile/ObscurityGauge'
import GenreDNA from '../components/profile/GenreDNA'
import DecadeChart from '../components/profile/DecadeChart'
import PersonalityBadge from '../components/profile/PersonalityBadge'
import LifetimeStats from '../components/profile/LifetimeStats'
import TasteMap from '../components/profile/TasteMap'
import ShareCardRenderer from '../components/share/ShareCardRenderer'
import ProfileShareCard from '../components/share/ProfileShareCard'
import SectionErrorBoundary from '../components/ui/SectionErrorBoundary'

export default function ProfilePage() {
  const { data, loading, error } = useSpotifyData('/api/v1/profile')
  const { data: recentSummary, loading: recentLoading, refetch: refetchRecent } = useSpotifyData('/api/v1/library/recent-summary')
  const [showShare, setShowShare] = useState(false)

  // Retry once if recent-summary is empty (backend sync may not have completed yet)
  const retriedRef = useRef(false)
  useEffect(() => {
    if (!recentLoading && !recentSummary?.tracks?.length && !retriedRef.current) {
      retriedRef.current = true
      const timer = setTimeout(() => {
        refetchRecent()
      }, 8000)
      return () => clearTimeout(timer)
    }
  }, [recentLoading, recentSummary, refetchRecent])

  if (loading) {
    return (
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-6">
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          {Array.from({ length: 4 }).map((_, i) => (
            <SkeletonKPICard key={i} />
          ))}
        </div>
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          <SkeletonCard />
          <SkeletonCard />
        </div>
      </div>
    )
  }

  if (error) {
    return (
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <div className="bg-surface rounded-xl p-8 text-center">
          <p className="text-red-400 text-sm">{error}</p>
        </div>
      </div>
    )
  }

  if (!data) return null

  const { user, metrics, personality } = data

  // Metrics not yet calculated
  if (!data.has_metrics) {
    return (
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {/* Header */}
        <ProfileHeader user={user} personality={null} onShare={null} />
        <div className="bg-surface rounded-xl p-8 flex flex-col items-center gap-3 mt-6">
          <Clock size={32} className="text-text-muted" />
          <p className="text-text-secondary text-sm text-center">
            Le tue metriche sono in fase di calcolo. Torna pi&ugrave; tardi!
          </p>
        </div>
      </div>
    )
  }

  return (
    <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-6">
      {/* Header */}
      <ProfileHeader user={user} personality={personality} onShare={() => setShowShare(true)} />

      {/* Lifetime KPIs */}
      <SectionErrorBoundary sectionName="LifetimeStats">
        <LifetimeStats metrics={metrics} />
      </SectionErrorBoundary>

      {/* Charts grid */}
      <StaggerContainer className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <StaggerItem>
          <SectionErrorBoundary sectionName="PersonalityBadge">
            <PersonalityBadge personality={personality} />
          </SectionErrorBoundary>
        </StaggerItem>
        <StaggerItem>
          <SectionErrorBoundary sectionName="ObscurityGauge">
            <ObscurityGauge score={metrics?.obscurity_score} />
          </SectionErrorBoundary>
        </StaggerItem>
        {metrics?.top_genres?.length > 0 && (
          <StaggerItem>
            <SectionErrorBoundary sectionName="GenreDNA">
              <GenreDNA topGenres={metrics.top_genres} />
            </SectionErrorBoundary>
          </StaggerItem>
        )}
        {metrics?.decade_distribution && Object.keys(metrics.decade_distribution).length > 0 && (
          <StaggerItem>
            <SectionErrorBoundary sectionName="DecadeChart">
              <DecadeChart decadeDistribution={metrics.decade_distribution} />
            </SectionErrorBoundary>
          </StaggerItem>
        )}
        {data.taste_map && data.taste_map.feature_mode !== 'insufficient' && data.taste_map.points?.length >= 3 && (
          <StaggerItem className="lg:col-span-2">
            <SectionErrorBoundary sectionName="TasteMap">
              <TasteMap
                points={data.taste_map.points}
                varianceExplained={data.taste_map.variance_explained}
                featureMode={data.taste_map.feature_mode}
                genreGroups={data.taste_map.genre_groups}
              />
            </SectionErrorBoundary>
          </StaggerItem>
        )}
      </StaggerContainer>

      {/* Ascolti recenti */}
      <SectionErrorBoundary sectionName="RecentSummary">
        {recentLoading ? (
          <SkeletonCard height="h-48" />
        ) : recentSummary?.tracks?.length > 0 && (
          <div className="glow-card bg-surface rounded-xl p-5">
            <div className="mb-4">
              <h3 className="text-text-primary font-display font-semibold">Ascolti recenti</h3>
              <p className="text-text-muted text-xs mt-0.5">
                {recentSummary.total_plays} ascolti totali
                {recentSummary.first_play_date && (
                  <span> &middot; dal {recentSummary.first_play_date}</span>
                )}
              </p>
            </div>
            <StaggerContainer className="space-y-1.5">
              {recentSummary.tracks.slice(0, 10).map((track, i) => (
                <StaggerItem key={track.track_spotify_id}>
                  <div className="flex items-center gap-3 py-1.5 px-2 rounded-lg hover:bg-surface-hover transition-colors">
                    <span className="text-text-muted text-xs font-mono w-5 text-right shrink-0">
                      {i + 1}
                    </span>
                    <div className="flex-1 min-w-0">
                      <p className="text-text-primary text-sm font-medium truncate">{track.track_name}</p>
                      <p className="text-text-muted text-xs truncate">{track.artist_name}</p>
                    </div>
                    <div className="flex items-center gap-2 shrink-0">
                      {track.consecutive_days > 1 && (
                        <span className="flex items-center gap-0.5 text-xs text-accent bg-accent/10 px-1.5 py-0.5 rounded-full">
                          <Flame className="w-3 h-3" />
                          {track.consecutive_days}g
                        </span>
                      )}
                      <span className="text-text-secondary text-xs font-mono">
                        {track.play_count}x
                      </span>
                    </div>
                  </div>
                </StaggerItem>
              ))}
            </StaggerContainer>
          </div>
        )}
      </SectionErrorBoundary>

      {/* Share modal */}
      <AnimatePresence>
        {showShare && (
          <ShareCardRenderer
            filename="wrap-profilo"
            onClose={() => setShowShare(false)}
          >
            <ProfileShareCard
              personality={personality}
              metrics={metrics}
              userName={user?.display_name}
            />
          </ShareCardRenderer>
        )}
      </AnimatePresence>
    </main>
  )
}

function ProfileHeader({ user, personality, onShare }) {
  return (
    <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
      <div className="flex items-center gap-4">
        {user?.avatar_url && (
          <img
            src={user.avatar_url}
            alt={user.display_name}
            className="w-14 h-14 rounded-full object-cover ring-2 ring-accent/30"
          />
        )}
        <div>
          <div className="flex items-center gap-3">
            <h1 className="text-2xl font-display font-bold text-text-primary">
              {user?.display_name || 'Profilo'}
            </h1>
            {personality && (
              <span className="text-sm bg-accent/10 text-accent px-2.5 py-0.5 rounded-full font-medium">
                {personality.emoji} {personality.archetype}
              </span>
            )}
          </div>
          <p className="text-text-secondary text-sm">Il tuo profilo musicale</p>
        </div>
      </div>
      {onShare && (
        <button
          onClick={onShare}
          className="flex items-center gap-2 px-4 py-2.5 bg-accent hover:bg-accent-hover text-white rounded-lg text-sm font-medium transition-colors"
        >
          <Share2 size={16} aria-hidden="true" />
          Condividi Profilo
        </button>
      )}
    </div>
  )
}
