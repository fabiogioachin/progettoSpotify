import { useCallback, useEffect, useRef, useState } from 'react'
import api from '../lib/api'

/**
 * Hook for on-demand audio feature analysis via polling.
 * POST /api/analyze-tracks → task_id → poll GET every 2.5s → progressive results.
 *
 * @param {Array<{id: string, name?: string, preview_url?: string, artists?: Array}>} tracks - Track objects (must include id, preview_url)
 * @param {boolean} enabled - If false, analysis won't start (default true)
 * @returns {{ features, progress, isAnalyzing, error, startAnalysis }}
 */
export function useAudioAnalysis(tracks, enabled = true) {
  const [features, setFeatures] = useState({})
  const [progress, setProgress] = useState({ total: 0, completed: 0, percent: 0 })
  const [isAnalyzing, setIsAnalyzing] = useState(false)
  const [error, setError] = useState(null)
  const taskIdRef = useRef(null)
  const timeoutRef = useRef(null)
  const mountedRef = useRef(true)
  const startedRef = useRef(false)

  // Cleanup on unmount
  useEffect(() => {
    mountedRef.current = true
    return () => {
      mountedRef.current = false
      if (timeoutRef.current) clearTimeout(timeoutRef.current)
    }
  }, [])

  // Stabilize dependency via joined IDs
  const trackIdsKey = tracks?.map(t => t.id).join(',') || ''

  const startAnalysis = useCallback(async () => {
    if (!tracks?.length || startedRef.current) return
    startedRef.current = true

    setIsAnalyzing(true)
    setError(null)
    setFeatures({})
    setProgress({ total: 0, completed: 0, percent: 0 })

    try {
      // Send track objects so the backend doesn't need to re-fetch from Spotify
      const trackPayload = tracks.map(t => ({
        id: t.id,
        name: t.name || '',
        artist: t.artists?.[0]?.name || t.artist || '',
        preview_url: t.preview_url || null,
      }))
      const { data } = await api.post('/api/analyze-tracks', {
        tracks: trackPayload,
      })

      if (!mountedRef.current) return
      taskIdRef.current = data.task_id
      setProgress({ total: data.total, completed: 0, percent: 0 })

      // Recursive setTimeout to avoid overlapping requests
      const poll = async () => {
        if (!mountedRef.current) return
        try {
          const { data: status } = await api.get(`/api/analyze-tracks/${taskIdRef.current}`)
          if (!mountedRef.current) return

          const percent = status.total > 0
            ? Math.round((status.completed / status.total) * 100)
            : 0
          setProgress({ total: status.total, completed: status.completed, percent })

          // Extract actual feature data (filter out unavailable/error sources)
          const validFeatures = {}
          for (const [tid, feat] of Object.entries(status.results || {})) {
            if (feat.source && !['unavailable', 'error', 'auth_error'].includes(feat.source)) {
              const { source: _source, ...featureData } = feat
              validFeatures[tid] = featureData
            }
          }
          setFeatures(validFeatures)

          if (status.status === 'completed' || status.status === 'error') {
            setIsAnalyzing(false)
            if (status.status === 'error') {
              setError('Errore durante l\'analisi audio')
            }
          } else {
            // Schedule next poll only after current one completes
            timeoutRef.current = setTimeout(poll, 2500)
          }
        } catch (err) {
          if (!mountedRef.current) return
          if (err.name !== 'CanceledError' && err.code !== 'ERR_CANCELED') {
            setIsAnalyzing(false)
            setError('Errore nel polling dell\'analisi')
          }
        }
      }

      // Start first poll
      timeoutRef.current = setTimeout(poll, 2500)
    } catch (err) {
      if (!mountedRef.current) return
      startedRef.current = false
      setIsAnalyzing(false)
      const message = err.response?.data?.detail || err.message || 'Errore nell\'avvio dell\'analisi'
      setError(message)
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps -- stabilized via trackIdsKey
  }, [trackIdsKey])

  // Auto-start when tracks change and enabled is true
  useEffect(() => {
    if (enabled && tracks?.length > 0) {
      startAnalysis()
    }
    return () => {
      if (timeoutRef.current) {
        clearTimeout(timeoutRef.current)
        timeoutRef.current = null
      }
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps -- trackIds changes captured via startAnalysis
  }, [enabled, startAnalysis])

  return { features, progress, isAnalyzing, error, startAnalysis }
}
