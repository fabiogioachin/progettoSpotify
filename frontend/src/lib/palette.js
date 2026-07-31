/**
 * L'unico posto del frontend in cui un colore è scritto per esteso.
 *
 * Da qui leggono tutti e tre i modi in cui l'applicazione colora qualcosa:
 *
 * - `tailwind.config.js`, da cui nascono le classi (`bg-accent`, `text-text-secondary`, …);
 * - `styles/globals.css`, che con `theme()` ne ricava le variabili CSS `--color-*`;
 * - `lib/chartTheme.js`, per i grafici Recharts, che vogliono stringhe di colore vere
 *   perché gli attributi SVG non risolvono `var(--…)`.
 *
 * Cambiare il colore d'accento del prodotto vuol dire cambiare la riga `accent` di
 * `COLORS`, e nessun'altra riga in nessun altro file.
 */

// Tinte di base. Il nome dice la tinta, non l'uso: il significato glielo dà chi le usa.
export const HUES = {
  indigo: '#6366f1',
  indigoLight: '#818cf8',
  indigoPale: '#a5b4fc',
  indigoDeep: '#4f46e5',
  emerald: '#10b981',
  emeraldLight: '#34d399',
  emeraldPale: '#6ee7b7',
  amber: '#f59e0b',
  amberLight: '#fbbf24',
  amberPale: '#fcd34d',
  orange: '#f97316',
  red: '#ef4444',
  pink: '#ec4899',
  pinkLight: '#f472b6',
  pinkPale: '#f9a8d4',
  cyan: '#06b6d4',
  cyanLight: '#22d3ee',
  cyanPale: '#67e8f9',
  violet: '#8b5cf6',
  violetDeep: '#7c3aed',
  purple: '#a855f7',
  teal: '#14b8a6',
  spotify: '#1DB954',
}

// Neutri, dal fondo pagina al testo. Scala dal più scuro al più chiaro.
export const NEUTRALS = {
  black: '#121212',
  gray900: '#181818',
  gray800: '#282828',
  gray700: '#3e3e3e',
  gray600: '#4b5563',
  gray500: '#6b7280',
  gray450: '#6a6a6a',
  gray400: '#8a8a8a',
  gray300: '#b3b3b3',
  gray200: '#e0e0e0',
  white: '#FFFFFF',
}

// Ruoli dell'interfaccia. È lo strato che conta: qui un colore ha un mestiere.
export const COLORS = {
  background: NEUTRALS.black,
  surface: NEUTRALS.gray900,
  surfaceHover: NEUTRALS.gray800,
  border: NEUTRALS.gray800,
  borderHover: NEUTRALS.gray700,
  accent: HUES.indigo,
  accentHover: HUES.indigoLight,
  accentPale: HUES.indigoPale,
  spotify: HUES.spotify,
  textPrimary: NEUTRALS.white,
  textSecondary: NEUTRALS.gray300,
  textMuted: NEUTRALS.gray400,
}

/**
 * Lo stesso colore con un'opacità. Serve dove ci vuole `rgba()` — aloni, ombre —
 * per non doverne riscrivere le componenti a mano, che è il modo con cui una copia
 * sfugge al cambio d'accento e resta indietro.
 */
export function withAlpha(hex, alpha) {
  const { r, g, b } = toRgb(hex)
  return `rgba(${r}, ${g}, ${b}, ${alpha})`
}

/** Le componenti numeriche di un colore, per chi deve interpolare invece che dipingere. */
export function toRgb(hex) {
  const n = parseInt(hex.slice(1), 16)
  return { r: (n >> 16) & 255, g: (n >> 8) & 255, b: n & 255 }
}
