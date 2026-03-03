import { useState } from 'react'
import { Copy, Check, ExternalLink, FileText } from 'lucide-react'
import { useSpotifyData } from '../../hooks/useSpotifyData'
import LoadingSpinner from '../ui/LoadingSpinner'

export default function ClaudeExportPanel() {
  const [copied, setCopied] = useState(false)
  const { data, loading, error, refetch } = useSpotifyData('/api/export/claude-prompt', {}, false)

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
      // Fallback
      const textarea = document.createElement('textarea')
      textarea.value = data.export_text
      document.body.appendChild(textarea)
      textarea.select()
      document.execCommand('copy')
      document.body.removeChild(textarea)
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    }
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

      {/* Genera */}
      {!data && !loading && (
        <button
          onClick={handleGenerate}
          className="w-full py-3 bg-accent hover:bg-accent-hover text-white rounded-lg font-medium transition-all duration-300 hover:shadow-lg hover:shadow-accent/20"
        >
          Genera Export
        </button>
      )}

      {loading && <LoadingSpinner size="sm" />}

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
          <div className="flex gap-3">
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
                  Copia negli appunti
                </>
              )}
            </button>

            <a
              href="https://claude.ai"
              target="_blank"
              rel="noopener noreferrer"
              className="flex-1 py-2.5 rounded-lg font-medium text-sm flex items-center justify-center gap-2 border border-border text-text-secondary hover:text-text-primary hover:border-border-hover transition-all duration-300"
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
