import { Link, useLocation } from 'react-router-dom'
import { motion } from 'framer-motion'
import { SearchX, LayoutDashboard } from 'lucide-react'

// Un indirizzo inventato puo' essere lungo quanto si vuole: qui lo mostriamo per
// far capire all'utente *quale* indirizzo non esiste, quindi va accorciato prima
// che sfondi il riquadro.
const MAX_PATH = 80

function shorten(path) {
  return path.length > MAX_PATH ? `${path.slice(0, MAX_PATH)}…` : path
}

export default function NotFoundPage() {
  const { pathname } = useLocation()

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3 }}
      className="max-w-lg mx-auto px-4 sm:px-6 lg:px-8 py-16 text-center"
    >
      <div className="w-14 h-14 rounded-2xl bg-accent/10 flex items-center justify-center mx-auto">
        <SearchX size={28} className="text-accent" />
      </div>

      <p className="mt-6 text-5xl font-display font-bold gradient-text">404</p>

      <h1 className="mt-2 text-2xl font-display font-bold text-text-primary">
        Questa pagina non esiste
      </h1>

      <p className="mt-3 text-sm text-text-secondary">
        L&apos;indirizzo che hai aperto non corrisponde a nessuna pagina
        dell&apos;applicazione. Potrebbe essere un refuso, o un collegamento
        salvato quando la pagina si chiamava in un altro modo.
      </p>

      <p className="mt-4 text-xs text-text-muted">
        Indirizzo cercato:{' '}
        <code className="px-1.5 py-0.5 rounded bg-surface border border-border text-text-secondary break-all">
          {shorten(pathname)}
        </code>
      </p>

      <Link
        to="/dashboard"
        className="mt-8 inline-flex items-center gap-2 px-5 py-2.5 min-h-[44px] bg-accent hover:bg-accent-hover text-white text-sm font-medium rounded-lg transition-colors"
      >
        <LayoutDashboard size={16} />
        Torna alla dashboard
      </Link>
    </motion.div>
  )
}
