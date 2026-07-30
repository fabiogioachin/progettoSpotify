import { useEffect } from 'react'
import { useLocation } from 'react-router-dom'

// react-router updates the location but never scrolls to the fragment: a push
// through <Link to="/page#section"> is not a fragment navigation, so the browser
// does nothing. The target is usually missing at that moment too — AnimatePresence
// mounts the destination only after the outgoing page finishes exiting, and the
// section itself appears when its fetch resolves. Hence a short retry window
// instead of a single lookup.
const RETRY_INTERVAL_MS = 100
const RETRY_WINDOW_MS = 3000

export function useHashScroll() {
  const { pathname, hash } = useLocation()

  useEffect(() => {
    const targetId = hash.slice(1)
    if (!targetId) return

    let timer = null
    let waited = 0

    const attempt = () => {
      const target = document.getElementById(targetId)
      if (target) {
        target.scrollIntoView({ behavior: 'smooth', block: 'start' })
        return
      }
      waited += RETRY_INTERVAL_MS
      if (waited < RETRY_WINDOW_MS) timer = setTimeout(attempt, RETRY_INTERVAL_MS)
    }

    attempt()
    return () => clearTimeout(timer)
  }, [pathname, hash])
}
