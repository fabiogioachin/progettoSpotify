import { useState, useEffect, useRef, useCallback } from 'react'
import api from '../lib/api'

const MAX_POLL_DURATION = 120_000 // 2 minutes

/**
 * POST/poll hook for progressive Wrapped computation.
 *
 * POST /api/v1/wrapped?time_range=X  → { task_id, total_services }
 * GET  /api/v1/wrapped/:taskId       → { status, phase, completed_services, total_services, results, available_slides, ... }
 *
 * Auto-starts on mount. Resets + restarts when timeRange changes.
 */
export function useWrappedTask(timeRange) {
  const [data, setData] = useState(null)
  const [isLoading, setIsLoading] = useState(true)
  const [isWaiting, setIsWaiting] = useState(false)
  const [waitSeconds, setWaitSeconds] = useState(0)
  const [error, setError] = useState(null)
  const [phase, setPhase] = useState('')
  const [completedServices, setCompletedServices] = useState(0)
  const [totalServices, setTotalServices] = useState(5)

  const taskIdRef = useRef(null)
  const timeoutRef = useRef(null)
  const mountedRef = useRef(true)
  const prevRangeRef = useRef(timeRange)
  const startTimeRef = useRef(null)

  const reset = useCallback(() => {
    if (timeoutRef.current) clearTimeout(timeoutRef.current)
    taskIdRef.current = null
    startTimeRef.current = null
    setData(null)
    setIsLoading(true)
    setIsWaiting(false)
    setWaitSeconds(0)
    setError(null)
    setPhase('')
    setCompletedServices(0)
  }, [])

  const poll = useCallback(async () => {
    if (!mountedRef.current || !taskIdRef.current) return

    // Check polling timeout
    if (startTimeRef.current && Date.now() - startTimeRef.current > MAX_POLL_DURATION) {
      setIsLoading(false)
      setError('Tempo massimo di elaborazione superato. I dati parziali sono mostrati.')
      return
    }

    try {
      const { data: status } = await api.get(`/api/v1/wrapped/${taskIdRef.current}`)
      if (!mountedRef.current) return

      setPhase(status.phase || '')
      setCompletedServices(status.completed_services || 0)
      setTotalServices(status.total_services || 5)

      if (status.results) {
        setData(status.results)
      }

      if (status.status === 'waiting') {
        setIsWaiting(true)
        setWaitSeconds(status.waiting_seconds || 0)
        timeoutRef.current = setTimeout(poll, 2000)
      } else if (status.status === 'completed') {
        setIsLoading(false)
        setIsWaiting(false)
      } else if (status.status === 'error') {
        setIsLoading(false)
        setIsWaiting(false)
        setError(status.error_detail || 'Errore durante l\'elaborazione')
      } else {
        // processing or pending — keep polling
        setIsWaiting(false)
        timeoutRef.current = setTimeout(poll, 1500)
      }
    } catch (err) {
      if (!mountedRef.current) return
      if (err.name === 'CanceledError' || err.code === 'ERR_CANCELED') return
      if (err?.response?.status === 401) {
        window.dispatchEvent(new CustomEvent('auth:expired'))
        return
      }
      setError('Errore di connessione')
      setIsLoading(false)
    }
  }, [])

  const start = useCallback(async () => {
    try {
      setIsLoading(true)
      setError(null)
      startTimeRef.current = Date.now()
      const { data: resp } = await api.post(`/api/v1/wrapped?time_range=${timeRange}`)
      if (!mountedRef.current) return
      taskIdRef.current = resp.task_id
      setTotalServices(resp.total_services || 5)
      timeoutRef.current = setTimeout(poll, 1000)
    } catch (err) {
      if (!mountedRef.current) return
      if (err?.response?.status === 401) {
        window.dispatchEvent(new CustomEvent('auth:expired'))
        return
      }
      setError(err.response?.data?.detail || err.message || 'Errore nell\'avvio dell\'elaborazione')
      setIsLoading(false)
    }
  }, [timeRange, poll])

  // Auto-start on mount
  useEffect(() => {
    mountedRef.current = true
    start()
    return () => {
      mountedRef.current = false
      if (timeoutRef.current) clearTimeout(timeoutRef.current)
    }
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

  // Restart on period change
  useEffect(() => {
    if (prevRangeRef.current !== timeRange) {
      prevRangeRef.current = timeRange
      reset()
      const t = setTimeout(() => start(), 50)
      return () => clearTimeout(t)
    }
  }, [timeRange, reset, start])

  return {
    data,
    availableSlides: data?.available_slides || ['intro'],
    isLoading,
    isComplete: !isLoading && !error,
    isWaiting,
    waitSeconds,
    phase,
    completedServices,
    totalServices,
    error,
  }
}
