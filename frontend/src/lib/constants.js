export const FEATURE_LABELS = {
  energy: 'Energia',
  valence: 'Positività',
  danceability: 'Ballabilità',
  acousticness: 'Acusticità',
  instrumentalness: 'Strumentalità',
  liveness: 'Dal vivo',
  speechiness: 'Parlato',
}

export const FEATURE_KEYS = Object.keys(FEATURE_LABELS)

export const TIME_PERIODS = [
  { value: 'short_term', label: 'Ultimo mese' },
  { value: 'medium_term', label: '6 mesi' },
  { value: 'long_term', label: 'Sempre' },
]
