import { useCallback, useEffect, useState } from 'react'
import { useParams } from 'react-router-dom'
import { UserPlus, X, HeartHandshake } from 'lucide-react'
import { AnimatePresence, motion } from 'framer-motion'
import { useAuth } from '../contexts/AuthContext'
import { useSpotifyData } from '../hooks/useSpotifyData'
import api from '../lib/api'
import { SkeletonCard, SkeletonGrid } from '../components/ui/Skeleton'
import { StaggerContainer, StaggerItem } from '../components/ui/StaggerContainer'
import FriendCard from '../components/social/FriendCard'
import CompatibilityMeter from '../components/social/CompatibilityMeter'
import TasteComparison from '../components/social/TasteComparison'
import Leaderboard from '../components/social/Leaderboard'
import InviteModal from '../components/social/InviteModal'
import SectionErrorBoundary from '../components/ui/SectionErrorBoundary'

export default function FriendsPage() {
  const { user } = useAuth()
  const { code } = useParams()

  const {
    data: friendsData,
    loading: friendsLoading,
    refetch: refetchFriends,
  } = useSpotifyData('/api/v1/social/friends')

  const {
    data: leaderboardData,
    loading: leaderboardLoading,
  } = useSpotifyData('/api/v1/social/leaderboard')

  const [selectedFriend, setSelectedFriend] = useState(null)
  const [comparison, setComparison] = useState(null)
  const [comparing, setComparing] = useState(false)
  const [compareError, setCompareError] = useState(null)
  const [inviteModalOpen, setInviteModalOpen] = useState(false)
  const [inviteCode, setInviteCode] = useState(null)
  const [toast, setToast] = useState(null)
  const [inviteError, setInviteError] = useState(null)
  const [removeError, setRemoveError] = useState(null)

  // Auto-accept invite code from URL
  useEffect(() => {
    if (!code) return
    let cancelled = false

    async function acceptInvite() {
      try {
        await api.post(`/api/v1/social/accept/${code}`)
        if (!cancelled) {
          setToast({ type: 'success', message: 'Amicizia accettata!' })
          refetchFriends()
        }
      } catch (err) {
        if (!cancelled) {
          const detail = err.response?.data?.detail || 'Invito non valido o scaduto'
          setToast({ type: 'error', message: detail })
        }
      }
    }

    acceptInvite()
    return () => { cancelled = true }
  }, [code, refetchFriends])

  // Auto-dismiss toast
  useEffect(() => {
    if (!toast) return
    const timer = setTimeout(() => setToast(null), 4000)
    return () => clearTimeout(timer)
  }, [toast])

  const handleInvite = useCallback(async () => {
    try {
      const { data } = await api.post('/api/v1/social/invite')
      setInviteCode(data.code)
      setInviteModalOpen(true)
    } catch (err) {
      if (err.response?.status === 401 || err.response?.status === 429) throw err
      console.error('Failed to create invite:', err)
      setInviteError('Errore nell\'invio dell\'invito. Riprova.')
      setTimeout(() => setInviteError(null), 5000)
    }
  }, [])

  const handleCompare = useCallback(async (friend) => {
    setSelectedFriend(friend)
    setComparing(true)
    setComparison(null)
    setCompareError(null)
    try {
      const { data } = await api.get(`/api/v1/social/compare/${friend.id}`)
      setComparison(data)
    } catch (err) {
      console.error('Comparison failed:', err)
      setComparison(null)
      setCompareError('Errore nel confronto, riprova.')
    } finally {
      setComparing(false)
    }
  }, [])

  const handleRemove = useCallback(async (friendId) => {
    try {
      await api.delete(`/api/v1/social/friends/${friendId}`)
      if (selectedFriend?.id === friendId) {
        setSelectedFriend(null)
        setComparison(null)
      }
      refetchFriends()
    } catch (err) {
      if (err.response?.status === 401 || err.response?.status === 429) throw err
      console.error('Remove failed:', err)
      setRemoveError('Errore nella rimozione dell\'amico. Riprova.')
      setTimeout(() => setRemoveError(null), 5000)
    }
  }, [selectedFriend, refetchFriends])

  const friends = friendsData?.friends || []

  return (
    <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-8">
      {/* Toast notification */}
      <AnimatePresence>
        {toast && (
          <motion.div
            initial={{ opacity: 0, y: -20 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -20 }}
            className={`fixed top-4 right-4 z-50 px-4 py-3 rounded-lg text-sm font-medium shadow-lg ${
              toast.type === 'success'
                ? 'bg-green-600/90 text-white'
                : 'bg-red-500/90 text-white'
            }`}
          >
            {toast.message}
          </motion.div>
        )}
      </AnimatePresence>

      {/* Header */}
      <div className="flex items-center justify-between gap-3">
        <h1 className="text-2xl font-display text-text-primary">Amici</h1>
        <button
          onClick={handleInvite}
          className="px-4 py-2.5 min-h-[44px] bg-accent hover:bg-accent-hover text-white text-sm font-medium rounded-lg transition-colors flex items-center gap-2 flex-shrink-0"
        >
          <UserPlus size={16} />
          <span className="hidden sm:inline">Invita un amico</span>
          <span className="sm:hidden">Invita</span>
        </button>
      </div>
      {inviteError && (
        <p className="text-red-400 text-sm mt-1">{inviteError}</p>
      )}

      {/* Friends grid */}
      <SectionErrorBoundary sectionName="FriendsGrid">
        {friendsLoading ? (
          <SkeletonGrid count={6} columns="grid-cols-1 md:grid-cols-2 lg:grid-cols-3" cardHeight="h-20" />
        ) : friends.length === 0 ? (
          /* Empty state — prominent invite CTA */
          <div className="bg-surface rounded-xl p-12 flex flex-col items-center gap-4 text-center">
            <HeartHandshake size={48} className="text-text-muted" />
            <p className="text-text-secondary text-sm max-w-sm">
              Non hai ancora amici. Invita qualcuno per confrontare i vostri gusti musicali!
            </p>
            <button
              onClick={handleInvite}
              className="px-5 py-2.5 bg-accent hover:bg-accent-hover text-white text-sm font-medium rounded-lg transition-colors flex items-center gap-2"
            >
              <UserPlus size={16} />
              Invita un amico
            </button>
          </div>
        ) : (
          <StaggerContainer className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {friends.map((friend) => (
              <StaggerItem key={friend.id}>
                <FriendCard
                  friend={friend}
                  onCompare={handleCompare}
                  onRemove={handleRemove}
                />
              </StaggerItem>
            ))}
          </StaggerContainer>
        )}
      </SectionErrorBoundary>
      {removeError && (
        <p className="text-red-400 text-sm mt-1">{removeError}</p>
      )}

      {/* Comparison panel */}
      <SectionErrorBoundary sectionName="FriendComparison">
      <AnimatePresence>
        {selectedFriend && (
          <motion.section
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: 'auto' }}
            exit={{ opacity: 0, height: 0 }}
            transition={{ duration: 0.3 }}
            className="bg-surface rounded-xl p-6 overflow-hidden"
          >
            {/* Comparison header */}
            <div className="flex items-center justify-between mb-6">
              <h2 className="text-lg font-display text-text-primary">
                Confronto con {selectedFriend.display_name}
              </h2>
              <button
                onClick={() => {
                  setSelectedFriend(null)
                  setComparison(null)
                }}
                className="p-1.5 text-text-muted hover:text-text-primary transition-colors"
                aria-label="Chiudi confronto"
              >
                <X size={18} />
              </button>
            </div>

            {comparing ? (
              <div className="flex justify-center py-8">
                <div className="w-8 h-8 border-2 border-accent border-t-transparent rounded-full animate-spin" />
              </div>
            ) : compareError ? (
              <p className="text-sm text-red-400 text-center py-4">{compareError}</p>
            ) : comparison ? (
              <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
                <div className="flex justify-center">
                  <CompatibilityMeter
                    score={comparison.score}
                    genreScore={comparison.genre_score}
                    artistScore={comparison.artist_score}
                    popularityScore={comparison.popularity_score}
                  />
                </div>
                <TasteComparison
                  unisce={comparison.unisce}
                  distingue={comparison.distingue}
                  userAName="Tu"
                  userBName={selectedFriend.display_name}
                />
              </div>
            ) : null}
          </motion.section>
        )}
      </AnimatePresence>
      </SectionErrorBoundary>

      {/* Leaderboard */}
      <SectionErrorBoundary sectionName="Leaderboard">
        {leaderboardLoading ? (
          <SkeletonCard height="h-64" />
        ) : (
          <Leaderboard
            rankings={leaderboardData}
            currentUserId={user?.id}
          />
        )}
      </SectionErrorBoundary>

      {/* Invite modal */}
      <InviteModal
        isOpen={inviteModalOpen}
        onClose={() => setInviteModalOpen(false)}
        inviteCode={inviteCode}
      />
    </main>
  )
}
