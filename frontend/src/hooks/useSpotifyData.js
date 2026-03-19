import { useCallback, useEffect, useRef, useState } from 'react'
import api from '../lib/api'

const CACHE_MAX_AGE_MS = 2 * 60 * 1000 // 2 minutes
const CACHE_MAX_ENTRIES = 100

/** Module-level in-memory cache: key → { data, timestamp } */
const responseCache = new Map()

function cacheKey(endpoint, params) {
  return endpoint + '::' + JSON.stringify(params)
}

/**
 * Hook generico per fetch dati da API Spotify.
 * Stale-while-revalidate: cached data returned immediately,
 * background refresh if older than CACHE_MAX_AGE_MS.
 *
 * @param {string} endpoint - L'endpoint API (es. '/api/library/top')
 * @param {object} params - Parametri query opzionali
 * @param {boolean} immediate - Se true, fetch automatico al mount
 */
export function useSpotifyData(endpoint, params = {}, immediate = true) {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  const stableParams = JSON.stringify(params)

  // Track whether the component is still mounted
  const mountedRef = useRef(true)
  useEffect(() => {
    mountedRef.current = true
    return () => { mountedRef.current = false }
  }, [])

  const fetchData = useCallback(async (overrideParams = {}, signal, { silent = false } = {}) => {
    if (!silent) setLoading(true)
    setError(null)
    try {
      const parsedParams = JSON.parse(stableParams)
      const mergedParams = { ...parsedParams, ...overrideParams }
      const { data: result } = await api.get(endpoint, {
        params: mergedParams,
        signal,
      })
      // Update cache on successful fetch — use mergedParams for correct key
      const key = cacheKey(endpoint, mergedParams)
      if (responseCache.size >= CACHE_MAX_ENTRIES) {
        const firstKey = responseCache.keys().next().value
        responseCache.delete(firstKey)
      }
      responseCache.set(key, { data: result, timestamp: Date.now() })
      if (mountedRef.current) {
        setData(result)
      }
      return result
    } catch (err) {
      if (err.name === 'CanceledError' || err.code === 'ERR_CANCELED') return null
      const message = err.response?.data?.detail || err.message || 'Errore nel caricamento'
      if (mountedRef.current) {
        setError(message)
      }
      return null
    } finally {
      if (mountedRef.current && !silent) {
        setLoading(false)
      }
    }
  }, [endpoint, stableParams])

  // refetch always bypasses cache
  const refetch = useCallback((overrideParams = {}, signal) => {
    return fetchData(overrideParams, signal)
  }, [fetchData])

  useEffect(() => {
    if (!immediate) return

    const parsedParams = JSON.parse(stableParams)
    const key = cacheKey(endpoint, parsedParams)
    const cached = responseCache.get(key)
    const now = Date.now()

    if (cached) {
      const age = now - cached.timestamp
      setData(cached.data)

      if (age < CACHE_MAX_AGE_MS) {
        // Fresh cache — no fetch needed
        setLoading(false)
        return
      }

      // Stale cache — return cached data immediately, revalidate silently in background
      setLoading(false)
      const controller = new AbortController()
      fetchData({}, controller.signal, { silent: true })
      return () => controller.abort()
    }

    // No cache — fetch normally
    const controller = new AbortController()
    fetchData({}, controller.signal)
    return () => controller.abort()
  }, [fetchData, immediate, endpoint, stableParams])

  return { data, loading, error, refetch }
}
