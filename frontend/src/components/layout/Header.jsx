import { Link, useLocation } from 'react-router-dom'
import { useAuth } from '../../contexts/AuthContext'
import { LogOut, Music2 } from 'lucide-react'

export default function Header() {
  const { user, logout } = useAuth()

  return (
    <header className="sticky top-0 z-50 bg-background/80 backdrop-blur-xl border-b border-border">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex items-center justify-between h-16">
          {/* Logo */}
          <Link to="/dashboard" className="flex items-center gap-2 group">
            <div className="w-8 h-8 bg-accent rounded-lg flex items-center justify-center group-hover:shadow-lg group-hover:shadow-accent/20 transition-all duration-300">
              <Music2 size={18} className="text-white" />
            </div>
            <span className="font-display font-bold text-lg hidden sm:block">
              <span className="gradient-text">Listening Intelligence</span>
            </span>
          </Link>

          {/* Nav */}
          <nav className="flex items-center gap-1" role="navigation" aria-label="Navigazione principale">
            <NavLink to="/dashboard">Dashboard</NavLink>
            <NavLink to="/playlists">Playlist</NavLink>
            <NavLink to="/discovery">Scopri</NavLink>
          </nav>

          {/* User */}
          <div className="flex items-center gap-3">
            {user?.avatar_url && (
              <img
                src={user.avatar_url}
                alt={user.display_name}
                className="w-8 h-8 rounded-full border border-border"
              />
            )}
            <span className="text-sm text-text-secondary hidden sm:block">
              {user?.display_name}
            </span>
            <button
              onClick={logout}
              className="p-2 rounded-lg text-text-muted hover:text-text-primary hover:bg-surface-hover transition-all duration-300"
              title="Esci"
              aria-label="Esci"
            >
              <LogOut size={18} />
            </button>
          </div>
        </div>
      </div>
    </header>
  )
}

function NavLink({ to, children }) {
  const location = useLocation()
  const isActive = location.pathname === to

  return (
    <Link
      to={to}
      className={`px-3 py-2 rounded-lg text-sm font-medium transition-all duration-300
        ${isActive
          ? 'text-accent bg-accent/10'
          : 'text-text-secondary hover:text-text-primary hover:bg-surface-hover'
        }`}
      aria-current={isActive ? 'page' : undefined}
    >
      {children}
    </Link>
  )
}
