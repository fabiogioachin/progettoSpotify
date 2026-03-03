export default function LoadingSpinner({ fullScreen = false, size = 'md' }) {
  const sizeClasses = {
    sm: 'w-5 h-5',
    md: 'w-8 h-8',
    lg: 'w-12 h-12',
  }

  const spinner = (
    <div
      className={`${sizeClasses[size]} border-2 border-border border-t-accent rounded-full animate-spin`}
    />
  )

  if (fullScreen) {
    return (
      <div className="flex items-center justify-center min-h-screen bg-background" role="status" aria-label="Caricamento in corso">
        {spinner}
      </div>
    )
  }

  return (
    <div className="flex items-center justify-center p-8" role="status" aria-label="Caricamento in corso">
      {spinner}
    </div>
  )
}
