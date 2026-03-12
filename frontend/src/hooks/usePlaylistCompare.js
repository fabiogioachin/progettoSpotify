import { useState, useRef, useCallback } from 'react'
import api from '../lib/api'

export function usePlaylistCompare() {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const controllerRef = useRef(null)

  const compare = useCallback(async (playlistIds) => {
    if (playlistIds.length < 2) return
    // Abort any in-flight request
    if (controllerRef.current) controllerRef.current.abort()
    const controller = new AbortController()
    controllerRef.current = controller

    setLoading(true)
    setError(null)
    try {
      const { data: result } = await api.get('/api/playlists/compare', {
        params: { ids: playlistIds.join(',') },
        signal: controller.signal,
      })
      setData(result)
    } catch (err) {
      if (err.name === 'CanceledError' || err.code === 'ERR_CANCELED') return
      setError(err.response?.data?.detail || err.message || 'Errore durante il confronto')
    } finally {
      setLoading(false)
    }
  }, [])

  const reset = useCallback(() => {
    if (controllerRef.current) controllerRef.current.abort()
    setData(null)
    setError(null)
  }, [])

  return { data, loading, error, compare, reset }
}
