import { useCallback } from 'react'
import { usePlaylistTask } from './usePlaylistTask'

export function usePlaylistCompare() {
  const {
    data,
    progress,
    isLoading: loading,
    isWaiting,
    waitSeconds,
    error,
    start,
    reset,
  } = usePlaylistTask({
    postUrl: '/api/v1/playlists/compare',
    pollUrl: (taskId) => `/api/v1/playlists/compare/${taskId}`,
  })

  const compare = useCallback((playlistIds) => {
    if (playlistIds.length < 2) return
    start({ playlist_ids: playlistIds })
  }, [start])

  return { data, loading, error, compare, reset, progress, isWaiting, waitSeconds }
}
