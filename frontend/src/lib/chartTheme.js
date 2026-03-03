// Colori e configurazione per i chart Recharts — dark theme

export const CHART_COLORS = {
  accent: '#6366f1',
  accentLight: '#818cf8',
  accentSoft: '#a5b4fc',
  spotify: '#1DB954',
  energy: '#f59e0b',
  valence: '#10b981',
  danceability: '#6366f1',
  acousticness: '#06b6d4',
  instrumentalness: '#8b5cf6',
  liveness: '#ec4899',
  speechiness: '#f97316',
  tempo: '#ef4444',
}

export const FEATURE_COLORS = {
  energy: '#f59e0b',
  valence: '#10b981',
  danceability: '#6366f1',
  acousticness: '#06b6d4',
  instrumentalness: '#8b5cf6',
  liveness: '#ec4899',
  speechiness: '#f97316',
}

export const PLAYLIST_COLORS = ['#6366f1', '#10b981', '#f59e0b', '#ec4899']

export const TOOLTIP_STYLE = {
  contentStyle: {
    backgroundColor: '#1a1a2e',
    border: '1px solid #2a2a45',
    borderRadius: '8px',
    color: '#f0f0f5',
    fontSize: '13px',
    boxShadow: '0 4px 20px rgba(0,0,0,0.4)',
  },
  labelStyle: {
    color: '#9ca3af',
    fontWeight: 600,
  },
}

export { FEATURE_LABELS as RADAR_LABELS } from './constants'
