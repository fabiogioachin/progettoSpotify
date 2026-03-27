import { Component } from 'react'
import { AlertTriangle } from 'lucide-react'

const MAX_RETRIES = 2

export default class SectionErrorBoundary extends Component {
  constructor(props) {
    super(props)
    this.state = { hasError: false, retryCount: 0 }
  }

  static getDerivedStateFromError() {
    return { hasError: true }
  }

  componentDidCatch(error, info) {
    const name = this.props.sectionName || 'Unknown'
    console.error(`[${name}]`, error, info)
  }

  handleRetry = () => {
    if (this.state.retryCount < MAX_RETRIES) {
      this.setState((prev) => ({
        hasError: false,
        retryCount: prev.retryCount + 1,
      }))
    }
  }

  render() {
    if (this.state.hasError) {
      const canRetry = this.state.retryCount < MAX_RETRIES

      return (
        <div className="flex flex-col items-center justify-center min-h-[12rem] rounded-xl bg-surface/50">
          <AlertTriangle size={40} className="text-yellow-500/60" />
          <p className="text-text-muted text-sm mt-3">Errore nel caricamento</p>
          {canRetry ? (
            <button
              onClick={this.handleRetry}
              className="text-accent hover:text-accent-hover text-sm mt-2 transition-colors"
            >
              Riprova
            </button>
          ) : (
            <p className="text-text-muted text-xs mt-2">Ricarica la pagina</p>
          )}
        </div>
      )
    }

    return this.props.children
  }
}
