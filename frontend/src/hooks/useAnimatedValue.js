import { useEffect, useRef, useState } from 'react'

/**
 * Hook per animare un valore numerico da 0 al target.
 * @param {number} target - Valore finale
 * @param {number} duration - Durata animazione in ms
 * @param {number} decimals - Cifre decimali
 */
export function useAnimatedValue(target, duration = 1000, decimals = 0) {
  const [value, setValue] = useState(0)
  const frameRef = useRef(null)
  const startTimeRef = useRef(null)

  useEffect(() => {
    if (target === null || target === undefined) return

    const start = 0
    startTimeRef.current = performance.now()

    function animate(now) {
      const elapsed = now - startTimeRef.current
      const progress = Math.min(elapsed / duration, 1)

      // Easing ease-out cubic
      const eased = 1 - Math.pow(1 - progress, 3)
      const current = start + (target - start) * eased

      setValue(Number(current.toFixed(decimals)))

      if (progress < 1) {
        frameRef.current = requestAnimationFrame(animate)
      }
    }

    frameRef.current = requestAnimationFrame(animate)

    return () => {
      if (frameRef.current) {
        cancelAnimationFrame(frameRef.current)
      }
    }
  }, [target, duration, decimals])

  return value
}
