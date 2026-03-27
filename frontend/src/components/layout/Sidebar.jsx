import { Link, useLocation } from 'react-router-dom'
import {
  LayoutDashboard,
  Compass,
  TrendingUp,
  Clock,
  Users,
  ListMusic,
  BarChart3,
  Sparkles,
  UserCircle,
  HeartHandshake,
  Menu,
  X,
  Shield,
  Settings,
} from 'lucide-react'
import { useState } from 'react'
import { AnimatePresence, motion } from 'framer-motion'
import { useAuth } from '../../contexts/AuthContext'

const NAV_SECTIONS = [
  {
    title: 'Principale',
    items: [
      { href: '/dashboard', icon: LayoutDashboard, label: 'Dashboard' },
      { href: '/profile', icon: UserCircle, label: 'Profilo' },
      { href: '/discovery', icon: Compass, label: 'Scopri' },
      { href: '/wrapped', icon: Sparkles, label: 'Il Tuo Wrapped', special: true },
    ],
  },
  {
    title: 'Analisi',
    items: [
      { href: '/evolution', icon: TrendingUp, label: 'Evoluzione Gusto' },
      { href: '/temporal', icon: Clock, label: 'Pattern Temporali' },
      { href: '/artists', icon: Users, label: 'Ecosistema Artisti' },
    ],
  },
  {
    title: 'Playlist',
    items: [
      { href: '/playlists', icon: ListMusic, label: 'Confronto' },
      { href: '/playlist-analytics', icon: BarChart3, label: 'Analisi' },
    ],
  },
  {
    title: 'Sociale',
    items: [
      { href: '/friends', icon: HeartHandshake, label: 'Amici' },
    ],
  },
]

export default function Sidebar() {
  const location = useLocation()
  const [mobileOpen, setMobileOpen] = useState(false)
  const { user } = useAuth()

  const sidebarContent = (
    <>
      {/* Close button (mobile) */}
      <div className="flex items-center justify-end p-3 lg:hidden">
        <button
          onClick={() => setMobileOpen(false)}
          className="p-2 rounded-lg text-text-muted hover:text-text-primary hover:bg-surface-hover transition-all"
          aria-label="Chiudi menu"
        >
          <X size={20} />
        </button>
      </div>

      {/* Spacer to account for header height on desktop */}
      <div className="hidden lg:block h-16 flex-shrink-0" />

      {/* Nav sections */}
      <nav className="flex-1 overflow-y-auto px-3 py-2 space-y-5">
        {NAV_SECTIONS.map((section) => (
          <div key={section.title}>
            <h4 className="text-text-muted text-[10px] font-semibold uppercase tracking-widest px-3 mb-2">
              {section.title}
            </h4>
            <div className="space-y-0.5">
              {section.items.map((item) => {
                const Icon = item.icon
                const isActive = location.pathname === item.href

                return (
                  <Link
                    key={item.href}
                    to={item.href}
                    onClick={() => setMobileOpen(false)}
                    className={`flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-all duration-200 relative
                      ${
                        item.special
                          ? isActive
                            ? 'bg-accent/20 text-accent'
                            : 'bg-accent/10 text-accent hover:bg-accent/20'
                          : isActive
                            ? 'text-text-primary bg-surface-hover'
                            : 'text-text-secondary hover:text-text-primary hover:bg-surface-hover'
                      }`}
                    aria-current={isActive ? 'page' : undefined}
                  >
                    {/* Active indicator bar */}
                    {isActive && (
                      <div className="absolute left-0 top-1/2 -translate-y-1/2 w-[3px] h-5 bg-accent rounded-r-full" />
                    )}
                    <Icon size={18} className={isActive || item.special ? 'text-accent' : ''} />
                    {item.label}
                  </Link>
                )
              })}
            </div>
          </div>
        ))}
      </nav>
      <div className="px-3 py-4 border-t border-border mt-auto space-y-1">
        {user?.is_admin && (
          <Link
            to="/admin"
            onClick={() => setMobileOpen(false)}
            className={`flex items-center gap-3 px-3 py-2 rounded-lg text-xs font-medium transition-all duration-200
              ${location.pathname === '/admin'
                ? 'text-text-primary bg-surface-hover'
                : 'text-text-muted hover:text-text-secondary hover:bg-surface-hover'
              }`}
          >
            <Settings size={14} />
            Admin
          </Link>
        )}
        <Link
          to="/privacy"
          onClick={() => setMobileOpen(false)}
          className={`flex items-center gap-3 px-3 py-2 rounded-lg text-xs font-medium transition-all duration-200
            ${location.pathname === '/privacy'
              ? 'text-text-primary bg-surface-hover'
              : 'text-text-muted hover:text-text-secondary hover:bg-surface-hover'
            }`}
        >
          <Shield size={14} />
          Privacy e dati
        </Link>
      </div>
    </>
  )

  return (
    <>
      {/* Mobile toggle button */}
      <button
        onClick={() => setMobileOpen(true)}
        className="lg:hidden fixed bottom-4 left-4 z-50 w-12 h-12 bg-accent rounded-full flex items-center justify-center shadow-lg shadow-accent/20 text-white"
        aria-label="Apri menu"
      >
        <Menu size={22} />
      </button>

      {/* Mobile overlay + sidebar with AnimatePresence */}
      <AnimatePresence>
        {mobileOpen && (
          <>
            <motion.div
              key="sidebar-overlay"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              transition={{ duration: 0.2 }}
              className="lg:hidden fixed inset-0 bg-black/60 z-40"
              onClick={() => setMobileOpen(false)}
            />
            <motion.aside
              key="sidebar-mobile"
              initial={{ x: -240 }}
              animate={{ x: 0 }}
              exit={{ x: -240 }}
              transition={{ duration: 0.25, ease: 'easeOut' }}
              className="lg:hidden fixed top-0 left-0 h-full z-50 w-60 bg-surface border-r border-border flex flex-col"
              aria-label="Navigazione laterale"
            >
              {sidebarContent}
            </motion.aside>
          </>
        )}
      </AnimatePresence>

      {/* Desktop sidebar — always visible, no animation needed */}
      <aside
        className="hidden lg:flex fixed top-0 left-0 h-full z-50 w-60 bg-surface border-r border-border flex-col"
        aria-label="Navigazione laterale"
      >
        {sidebarContent}
      </aside>
    </>
  )
}
