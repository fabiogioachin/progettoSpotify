import { useAuth } from '../contexts/AuthContext'
import { BarChart3, Music2, Sparkles, TrendingUp } from 'lucide-react'

export default function LoginPage() {
  const { login } = useAuth()

  return (
    <div className="min-h-screen flex flex-col items-center justify-center px-4 relative overflow-hidden">
      {/* Animated background */}
      <div className="absolute inset-0 overflow-hidden pointer-events-none">
        {/* Gradient orbs */}
        <div className="absolute top-1/4 left-1/4 w-96 h-96 bg-accent/10 rounded-full blur-[120px] animate-float" />
        <div
          className="absolute bottom-1/4 right-1/4 w-80 h-80 bg-purple-600/10 rounded-full blur-[100px] animate-float"
          style={{ animationDelay: '2s' }}
        />

        {/* Audio wave bars */}
        <div className="absolute bottom-0 left-0 right-0 flex items-end justify-center gap-1 h-40 opacity-20 px-8">
          {Array.from({ length: 60 }).map((_, i) => (
            <div
              key={i}
              className="audio-bar w-1 min-h-[4px]"
              style={{
                animationDelay: `${i * 0.05}s`,
                animationDuration: `${1 + Math.random() * 1.5}s`,
                opacity: 0.3 + Math.random() * 0.7,
              }}
            />
          ))}
        </div>
      </div>

      {/* Content */}
      <div className="relative z-10 text-center max-w-lg mx-auto animate-fade-in">
        {/* Logo */}
        <div className="flex items-center justify-center gap-3 mb-8">
          <div className="w-14 h-14 bg-accent rounded-2xl flex items-center justify-center shadow-xl shadow-accent/20 animate-pulse-glow">
            <Music2 size={28} className="text-white" />
          </div>
        </div>

        {/* Title */}
        <h1 className="text-5xl sm:text-6xl font-display font-bold mb-4 leading-tight">
          <span className="gradient-text">Listening</span>
          <br />
          <span className="text-text-primary">Intelligence</span>
        </h1>

        <p className="text-text-secondary text-lg mb-10 max-w-md mx-auto">
          Scopri il tuo profilo musicale. Analisi avanzata dei tuoi ascolti Spotify con insight personalizzati.
        </p>

        {/* Features */}
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 mb-10">
          <FeatureCard
            icon={BarChart3}
            title="Analisi Audio"
            desc="Profilo dettagliato delle tue feature musicali"
          />
          <FeatureCard
            icon={TrendingUp}
            title="Trend"
            desc="Come evolve il tuo gusto nel tempo"
          />
          <FeatureCard
            icon={Sparkles}
            title="Discovery"
            desc="Scopri nuovi artisti affini al tuo stile"
          />
        </div>

        {/* CTA */}
        <button
          onClick={login}
          className="inline-flex items-center gap-3 px-8 py-4 bg-spotify hover:bg-spotify/90 text-white rounded-full font-semibold text-lg transition-all duration-300 hover:shadow-xl hover:shadow-spotify/20 hover:scale-105 active:scale-100"
        >
          <SpotifyIcon />
          Connetti Spotify
        </button>

        <p className="text-text-muted text-xs mt-4">
          Connessione sicura via OAuth. Non salviamo la tua password.
        </p>
      </div>
    </div>
  )
}

function FeatureCard({ icon: Icon, title, desc }) {
  return (
    <div className="glow-card bg-surface/50 rounded-xl p-4 text-center">
      <Icon size={24} className="text-accent mx-auto mb-2" />
      <h3 className="text-text-primary text-sm font-semibold mb-1">{title}</h3>
      <p className="text-text-muted text-xs">{desc}</p>
    </div>
  )
}

function SpotifyIcon() {
  return (
    <svg width="24" height="24" viewBox="0 0 24 24" fill="currentColor">
      <path d="M12 0C5.4 0 0 5.4 0 12s5.4 12 12 12 12-5.4 12-12S18.66 0 12 0zm5.521 17.34c-.24.359-.66.48-1.021.24-2.82-1.74-6.36-2.101-10.561-1.141-.418.122-.779-.179-.899-.539-.12-.421.18-.78.54-.9 4.56-1.021 8.52-.6 11.64 1.32.42.18.479.659.301 1.02zm1.44-3.3c-.301.42-.841.6-1.262.3-3.239-1.98-8.159-2.58-11.939-1.38-.479.12-1.02-.12-1.14-.6-.12-.48.12-1.021.6-1.141C9.6 9.9 15 10.561 18.72 12.84c.361.181.54.78.241 1.2zm.12-3.36C15.24 8.4 8.82 8.16 5.16 9.301c-.6.179-1.2-.181-1.38-.721-.18-.601.18-1.2.72-1.381 4.26-1.26 11.28-1.02 15.721 1.621.539.3.719 1.02.419 1.56-.299.421-1.02.599-1.559.3z" />
    </svg>
  )
}
