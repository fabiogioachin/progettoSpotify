import { Component } from 'react'

export default class ErrorBoundary extends Component {
  constructor(props) {
    super(props)
    this.state = { hasError: false }
  }

  static getDerivedStateFromError() {
    return { hasError: true }
  }

  componentDidCatch(error, errorInfo) {
    console.error('React ErrorBoundary caught:', error, errorInfo)
  }

  render() {
    if (this.state.hasError) {
      return (
        <div className="min-h-screen bg-background flex items-center justify-center p-8">
          <div className="text-center max-w-md">
            <h2 className="text-xl font-display font-bold text-text-primary mb-2">
              Qualcosa è andato storto
            </h2>
            <p className="text-text-muted text-sm mb-4">
              Si è verificato un errore inatteso. Riprova.
            </p>
            <button
              onClick={() => window.location.reload()}
              className="px-6 py-2 bg-accent hover:bg-accent-hover text-white rounded-lg font-medium transition-all"
            >
              Ricarica pagina
            </button>
          </div>
        </div>
      )
    }
    return this.props.children
  }
}
