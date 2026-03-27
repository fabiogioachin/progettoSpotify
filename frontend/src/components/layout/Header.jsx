import { useState, useEffect } from 'react'
import { Link } from 'react-router-dom'
import { useAuth } from '../../contexts/AuthContext'
import { LogOut, Music2, Activity } from 'lucide-react'

export default function Header() {
  const { user, logout } = useAuth()
  const [usage, setUsage] = useState({ current: 0, max: 25, pct: 0 })

  useEffect(() => {
    const handler = (e) => setUsage(e.detail)
    window.addEventListener('api:usage', handler)
    return () => window.removeEventListener('api:usage', handler)
  }, [])

  const usageColor = usage.pct > 85
    ? 'text-red-400 bg-red-500/10 border-red-500/20'
    : usage.pct > 60
      ? 'text-amber-400 bg-amber-500/10 border-amber-500/20'
      : 'text-emerald-400 bg-emerald-500/10 border-emerald-500/20'

  return (
    <header className="sticky top-0 z-40 bg-background/80 backdrop-blur-xl border-b border-border lg:pl-60">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex items-center justify-between h-16">
          {/* Logo */}
          <Link to="/dashboard" className="flex items-center gap-2 group">
            <div className="w-8 h-8 bg-accent rounded-lg flex items-center justify-center group-hover:shadow-lg group-hover:shadow-accent/20 transition-all duration-300">
              <Music2 size={18} className="text-white" />
            </div>
            <span className="font-display font-bold text-lg hidden sm:block">
              <span className="gradient-text">Wrap</span>
            </span>
          </Link>

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
            <div
              className={`hidden sm:flex items-center gap-1.5 px-2.5 py-1 rounded-full border text-xs font-medium ${usageColor}`}
              title={`Budget API: ${usage.current}/${usage.max} chiamate negli ultimi 30s`}
            >
              <Activity size={12} />
              <span>{usage.current}/{usage.max}</span>
            </div>
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
