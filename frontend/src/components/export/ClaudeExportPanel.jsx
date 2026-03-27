import { useState } from 'react'
import { Copy, Check, ExternalLink, FileText, Download } from 'lucide-react'
import { useSpotifyData } from '../../hooks/useSpotifyData'
import { SkeletonCard } from '../ui/Skeleton'

const DATA_BADGES = [
  { label: 'Brani', color: 'bg-accent/10 text-accent' },
  { label: 'Artisti', color: 'bg-emerald-400/10 text-emerald-400' },
  { label: 'Evoluzione', color: 'bg-amber-400/10 text-amber-400' },
  { label: 'Rete', color: 'bg-cyan-400/10 text-cyan-400' },
  { label: 'Temporale', color: 'bg-pink-400/10 text-pink-400' },
]

export default function ClaudeExportPanel() {
  const [copied, setCopied] = useState(false)
  const { data, loading, error, refetch } = useSpotifyData('/api/v1/export/claude-prompt', {}, false)

  async function handleGenerate() {
    await refetch()
  }

  async function handleCopy() {
    if (!data?.export_text) return
    try {
      await navigator.clipboard.writeText(data.export_text)
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    } catch {
      const blob = new Blob([data.export_text], { type: 'text/plain' })
      const clipboardItem = new ClipboardItem({ 'text/plain': blob })
      await navigator.clipboard.write([clipboardItem]).catch(() => {
        window.prompt('Copia il testo:', data.export_text)
      })
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    }
  }

  function handleDownload() {
    if (!data?.export_text) return
    const blob = new Blob([data.export_text], { type: 'text/markdown' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = 'spotify-listening-intelligence.md'
    document.body.appendChild(a)
    a.click()
    document.body.removeChild(a)
    URL.revokeObjectURL(url)
  }

  return (
    <div className="glow-card bg-surface rounded-xl p-6">
      <div className="flex items-center gap-3 mb-4">
        <div className="w-10 h-10 rounded-lg bg-accent/10 flex items-center justify-center">
          <FileText size={20} className="text-accent" />
        </div>
        <div>
          <h3 className="text-text-primary font-display font-semibold">Export per Claude AI</h3>
          <p className="text-text-muted text-sm">
            Genera un prompt ottimizzato con i tuoi dati di ascolto
          </p>
        </div>
      </div>

      {/* Data badges */}
      <div className="flex flex-wrap gap-1.5 mb-4">
        {DATA_BADGES.map(({ label, color }) => (
          <span key={label} className={`text-[10px] font-medium px-2 py-0.5 rounded-full ${color}`}>
            {label}
          </span>
        ))}
      </div>

      {/* Genera */}
      {!data && !loading && (
        <button
          onClick={handleGenerate}
          className="w-full py-3 bg-accent hover:bg-accent-hover text-white rounded-lg font-medium transition-all duration-300 hover:shadow-lg hover:shadow-accent/20"
        >
          Genera Export
        </button>
      )}

      {loading && <SkeletonCard height="h-32" />}

      {error && (
        <div className="text-red-400 text-sm bg-red-400/10 p-3 rounded-lg">
          {error}
        </div>
      )}

      {data && (
        <div className="space-y-4">
          {/* Preview */}
          <div className="bg-background rounded-lg p-4 max-h-60 overflow-y-auto">
            <pre className="text-text-secondary text-xs whitespace-pre-wrap font-mono">
              {data.data_preview || data.export_text?.slice(0, 500) + '...'}
            </pre>
          </div>

          {/* Token estimate */}
          <div className="text-text-muted text-xs">
            Token stimati: ~{data.estimated_tokens?.toLocaleString('it-IT')}
          </div>

          {/* Actions */}
          <div className="flex gap-2">
            <button
              onClick={handleCopy}
              className={`flex-1 py-2.5 rounded-lg font-medium text-sm flex items-center justify-center gap-2 transition-all duration-300
                ${copied
                  ? 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/30'
                  : 'bg-accent hover:bg-accent-hover text-white hover:shadow-lg hover:shadow-accent/20'
                }`}
            >
              {copied ? (
                <>
                  <Check size={16} />
                  Copiato!
                </>
              ) : (
                <>
                  <Copy size={16} />
                  Copia
                </>
              )}
            </button>

            <button
              onClick={handleDownload}
              className="py-2.5 px-4 rounded-lg font-medium text-sm flex items-center justify-center gap-2 border border-border text-text-secondary hover:text-text-primary hover:border-surface-hover transition-all duration-300"
              title="Scarica come file .md"
            >
              <Download size={16} />
              .md
            </button>

            <a
              href="https://claude.ai"
              target="_blank"
              rel="noopener noreferrer"
              className="flex-1 py-2.5 rounded-lg font-medium text-sm flex items-center justify-center gap-2 border border-border text-text-secondary hover:text-text-primary hover:border-surface-hover transition-all duration-300"
            >
              <ExternalLink size={16} />
              Apri Claude
            </a>
          </div>

          {/* Rigenera */}
          <button
            onClick={handleGenerate}
            className="w-full py-2 text-text-muted text-sm hover:text-text-secondary transition-colors"
          >
            Rigenera
          </button>
        </div>
      )}
    </div>
  )
}
