import { useState } from 'react'
import api from '../lib/api'

export function usePlaylistCompare() {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  async function compare(playlistIds) {
    if (playlistIds.length < 2) return
    setLoading(true)
    setError(null)
    try {
      const { data: result } = await api.get('/api/playlists/compare', {
        params: { ids: playlistIds.join(',') },
      })
      setData(result)
    } catch (err) {
      setError(err.response?.data?.detail || err.message || 'Errore durante il confronto')
    } finally {
      setLoading(false)
    }
  }

  function reset() {
    setData(null)
    setError(null)
  }

  return { data, loading, error, compare, reset }
}
