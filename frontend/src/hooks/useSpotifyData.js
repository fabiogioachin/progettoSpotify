import { useCallback, useEffect, useState } from 'react'
import api from '../lib/api'

/**
 * Hook generico per fetch dati da API Spotify.
 * @param {string} endpoint - L'endpoint API (es. '/api/library/top')
 * @param {object} params - Parametri query opzionali
 * @param {boolean} immediate - Se true, fetch automatico al mount
 */
export function useSpotifyData(endpoint, params = {}, immediate = true) {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  const stableParams = JSON.stringify(params)

  const fetchData = useCallback(async (overrideParams = {}, signal) => {
    setLoading(true)
    setError(null)
    try {
      const { data: result } = await api.get(endpoint, {
        params: { ...params, ...overrideParams },
        signal,
      })
      setData(result)
      return result
    } catch (err) {
      if (err.name === 'CanceledError' || err.code === 'ERR_CANCELED') return null
      const message = err.response?.data?.detail || err.message || 'Errore nel caricamento'
      setError(message)
      return null
    } finally {
      setLoading(false)
    }
  }, [endpoint, stableParams])

  useEffect(() => {
    if (!immediate) return
    const controller = new AbortController()
    fetchData({}, controller.signal)
    return () => controller.abort()
  }, [fetchData, immediate])

  return { data, loading, error, refetch: fetchData }
}
