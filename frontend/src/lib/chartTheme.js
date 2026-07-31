// Colori e configurazione per i chart Recharts — dark theme Spotify-style.
// Nessun colore è scritto qui: arrivano tutti da `palette.js`, che è l'unico posto
// in cui un colore esiste per esteso. Qui si dice soltanto a che cosa servono.

import { COLORS, HUES, NEUTRALS, toRgb } from './palette'

// --- La cornice comune a tutti i grafici: griglia, assi, tooltip, legenda ---

export const GRID_COLOR = COLORS.border
/** Colore delle tacche degli assi. La dimensione del testo la sceglie ogni grafico. */
export const AXIS_TICK_COLOR = COLORS.textSecondary
/** Colore del nome dell'asse, un gradino più spento delle tacche. */
export const AXIS_LABEL_COLOR = NEUTRALS.gray500
export const AXIS_LINE = { stroke: GRID_COLOR }
export const LEGEND_STYLE = { color: AXIS_TICK_COLOR, fontSize: 12 }

export const TOOLTIP_STYLE = {
  contentStyle: {
    backgroundColor: COLORS.surfaceHover,
    border: `1px solid ${COLORS.borderHover}`,
    borderRadius: '8px',
    color: COLORS.textPrimary,
    fontSize: '13px',
    boxShadow: '0 4px 20px rgba(0,0,0,0.4)',
  },
  labelStyle: {
    color: COLORS.textSecondary,
    fontWeight: 600,
  },
}

// --- Serie di dati ---

/** Una tinta per caratteristica audio, stabile fra i grafici che le mostrano. */
export const FEATURE_COLORS = {
  energy: HUES.amber,
  valence: HUES.emerald,
  danceability: HUES.indigo,
  acousticness: HUES.cyan,
  instrumentalness: HUES.violet,
  liveness: HUES.pink,
  speechiness: HUES.orange,
}

/** Fino a quattro playlist a confronto. */
export const PLAYLIST_COLORS = [HUES.indigo, HUES.emerald, HUES.amber, HUES.pink]

/** Le cerchie della rete artisti: dieci tinte ben distinte fra loro. */
export const CLUSTER_COLORS = [
  HUES.indigo, HUES.spotify, HUES.amber, HUES.pink, HUES.cyan,
  HUES.violet, HUES.red, HUES.emerald, HUES.orange, HUES.teal,
]

/** I generi della ciambella: cinque famiglie, tre gradazioni ciascuna. */
export const GENRE_COLORS = [
  HUES.indigo, HUES.indigoLight, HUES.indigoPale,
  HUES.emerald, HUES.emeraldLight, HUES.emeraldPale,
  HUES.amber, HUES.amberLight, HUES.amberPale,
  HUES.pink, HUES.pinkLight, HUES.pinkPale,
  HUES.cyan, HUES.cyanLight, HUES.cyanPale,
]

/** I sei generi principali della mappa del gusto. */
export const TASTE_MAP_COLORS = [
  HUES.indigo, HUES.spotify, HUES.amber, HUES.pink, HUES.cyan, HUES.violet,
]

/** Il punto di chi non rientra in nessuna delle categorie mostrate. */
export const UNCATEGORIZED_COLOR = NEUTRALS.gray600

/** Artisti presenti in uno, due o tutti e tre i periodi: dal tiepido al caldo. */
export const OVERLAP_COLORS = [NEUTRALS.gray450, COLORS.accent, HUES.spotify]

/** Quanto sei fuori dal mainstream: da noto a introvabile. */
export const OBSCURITY_COLORS = [HUES.emerald, HUES.indigo, HUES.purple]

// --- Rampe continue ---

/**
 * La mappa di calore degli ascolti. `HEATMAP_RAMP` colora le celle interpolando fra
 * le fermate, `HEATMAP_GRADIENT` disegna la legenda: vengono dalla stessa lista, quindi
 * la legenda non può più dire un colore diverso da quello che la griglia mostra.
 */
export const HEATMAP_GRADIENT = [HUES.spotify, HUES.amber, HUES.red, HUES.purple]

const HEATMAP_STOPS = [0, 0.33, 0.66, 1]

export const HEATMAP_RAMP = HEATMAP_GRADIENT.map((hex, i) => ({
  pos: HEATMAP_STOPS[i],
  ...toRgb(hex),
}))

/** La fiamma dello streak: bordo esterno e cuore interno. */
export const FLAME_OUTER = [HUES.amber, HUES.orange, HUES.red]
export const FLAME_INNER = [HUES.amberLight, HUES.amber]

export { FEATURE_LABELS as RADAR_LABELS } from './constants'
