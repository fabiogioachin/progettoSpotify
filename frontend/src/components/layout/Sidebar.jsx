import { Link, useLocation } from 'react-router-dom'
import { BarChart3, Compass, LayoutDashboard, ListMusic } from 'lucide-react'

const NAV_ITEMS = [
  { href: '/dashboard', icon: LayoutDashboard, label: 'Dashboard' },
  { href: '/playlists', icon: ListMusic, label: 'Playlist' },
  { href: '/discovery', icon: Compass, label: 'Scopri' },
]

export default function Sidebar() {
  const location = useLocation()

  return (
    <aside className="hidden lg:flex flex-col w-16 bg-surface border-r border-border items-center py-4 gap-2" aria-label="Navigazione laterale">
      {NAV_ITEMS.map((item) => {
        const Icon = item.icon
        const isActive = location.pathname === item.href

        return (
          <Link
            key={item.href}
            to={item.href}
            className={`w-10 h-10 rounded-lg flex items-center justify-center transition-all duration-300 group relative
              ${isActive
                ? 'bg-accent text-white shadow-lg shadow-accent/20'
                : 'text-text-muted hover:text-text-primary hover:bg-surface-hover'
              }`}
            title={item.label}
            aria-label={item.label}
            aria-current={isActive ? 'page' : undefined}
          >
            <Icon size={20} />
            {/* Tooltip */}
            <span className="absolute left-14 bg-surface-hover text-text-primary text-xs px-2 py-1 rounded opacity-0 group-hover:opacity-100 transition-opacity whitespace-nowrap pointer-events-none">
              {item.label}
            </span>
          </Link>
        )
      })}
    </aside>
  )
}
