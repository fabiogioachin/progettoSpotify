import { useCallback, useEffect, useRef, useState } from 'react'
import api from '../lib/api'

/**
 * Generic hook for progressive playlist loading via POST-start/GET-poll.
 *
 * @param {Object} config
 * @param {string} config.postUrl — endpoint to POST to start the task
 * @param {Function} config.pollUrl — (taskId) => poll endpoint URL
 * @param {number} [config.pollInterval=2000] — ms between polls
 * @returns {{ data, progress, isLoading, isWaiting, waitSeconds, error, start, reset }}
 */
const MAX_POLL_DURATION = 180_000 // 3 minutes

export function usePlaylistTask({ postUrl, pollUrl, pollInterval = 2000 }) {
  const [data, setData] = useState(null)
  const [progress, setProgress] = useState({ total: 0, completed: 0, percent: 0, phase: '' })
  const [isLoading, setIsLoading] = useState(false)
  const [isWaiting, setIsWaiting] = useState(false)
  const [waitSeconds, setWaitSeconds] = useState(0)
  const [error, setError] = useState(null)
  const taskIdRef = useRef(null)
  const timeoutRef = useRef(null)
  const mountedRef = useRef(true)
  const startTimeRef = useRef(null)

  useEffect(() => {
    mountedRef.current = true
    return () => {
      mountedRef.current = false
      if (timeoutRef.current) clearTimeout(timeoutRef.current)
    }
  }, [])

  const reset = useCallback(() => {
    if (timeoutRef.current) clearTimeout(timeoutRef.current)
    taskIdRef.current = null
    startTimeRef.current = null
    setData(null)
    setProgress({ total: 0, completed: 0, percent: 0, phase: '' })
    setIsLoading(false)
    setIsWaiting(false)
    setWaitSeconds(0)
    setError(null)
  }, [])

  const start = useCallback(async (body) => {
    reset()
    setIsLoading(true)
    startTimeRef.current = Date.now()

    try {
      const { data: startRes } = await api.post(postUrl, body)
      if (!mountedRef.current) return

      taskIdRef.current = startRes.task_id
      setProgress(prev => ({ ...prev, total: startRes.total_playlists || 0 }))

      const poll = async () => {
        if (!mountedRef.current) return

        // Check polling timeout
        if (Date.now() - startTimeRef.current > MAX_POLL_DURATION) {
          setIsLoading(false)
          setError('Tempo massimo di elaborazione superato. I dati parziali sono mostrati.')
          return
        }

        try {
          const { data: status } = await api.get(pollUrl(taskIdRef.current))
          if (!mountedRef.current) return

          const percent = status.total_playlists > 0
            ? Math.round((status.completed_playlists / status.total_playlists) * 100)
            : 0
          setProgress({
            total: status.total_playlists,
            completed: status.completed_playlists,
            percent,
            phase: status.phase || '',
          })

          // Handle waiting state (budget pause)
          if (status.status === 'waiting') {
            setIsWaiting(true)
            setWaitSeconds(status.waiting_seconds || 0)
          } else {
            setIsWaiting(false)
            setWaitSeconds(0)
          }

          // Update partial/complete results
          if (status.results) {
            setData(status.results)
          }

          if (status.status === 'completed') {
            setIsLoading(false)
            setIsWaiting(false)
          } else if (status.status === 'error') {
            setIsLoading(false)
            setIsWaiting(false)
            setError(status.error_detail || 'Errore durante l\'elaborazione')
          } else {
            timeoutRef.current = setTimeout(poll, pollInterval)
          }
        } catch (err) {
          if (!mountedRef.current) return
          if (err.name !== 'CanceledError' && err.code !== 'ERR_CANCELED') {
            setIsLoading(false)
            setError('Errore nel polling')
          }
        }
      }

      timeoutRef.current = setTimeout(poll, pollInterval)
    } catch (err) {
      if (!mountedRef.current) return
      setIsLoading(false)
      setError(err.response?.data?.detail || err.message || 'Errore nell\'avvio dell\'analisi')
    }
  }, [postUrl, pollUrl, pollInterval, reset])

  return { data, progress, isLoading, isWaiting, waitSeconds, error, start, reset }
}
