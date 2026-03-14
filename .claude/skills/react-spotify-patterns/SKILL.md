---
name: react-spotify-patterns
description: Frontend patterns for this React + Vite + Tailwind project. Data fetching, auth flow, component conventions, styling system, and UI patterns.
---

# React Spotify Patterns

Patterns codificati in questo progetto. Leggere PRIMA di scrivere qualsiasi codice frontend.

## Data Fetching — useSpotifyData

Unico hook per tutti i fetch API. Non usare `useEffect` + `fetch` diretto.

```jsx
import { useSpotifyData } from '../hooks/useSpotifyData'

function MyPage() {
  const { data, loading, error, refetch } = useSpotifyData('/api/endpoint', { time_range: 'short_term' })

  if (loading) return <LoadingSpinner />
  if (error) return <ErrorMessage message={error} />
  if (!data) return null

  return <div>{/* render data */}</div>
}
```

- `endpoint`: stringa (es. `/api/analytics/features`)
- `params`: oggetto query params (stabilizzato internamente con `JSON.stringify`)
- `immediate`: default `true` (fetch al mount). Passare `false` per fetch manuale con `refetch()`
- AbortController integrato: cancella automaticamente al unmount
- Errori: `err.response?.data?.detail` → `err.message` → fallback `"Errore nel caricamento"`

## Auth Flow

### AuthContext + auth:expired

```
AuthProvider (mount) → GET /auth/me → setUser
    ↓
API call → 401 → axios interceptor → window.dispatchEvent('auth:expired')
    ↓
AuthContext listener → setUser(null) → ProtectedRoute redirige a login
```

- Login: `window.location.href = '/auth/spotify/login'` (redirect, non SPA navigation)
- Logout: `POST /auth/logout` → `setUser(null)` → redirect `/`
- Non servono token nel frontend: l'auth è cookie-based (httpOnly)

### Axios Interceptor (lib/api.js)

```
Response error:
  429 + Retry-After ≤ 30s → retry automatico (max 2 volte)
  429 + Retry-After > 30s → reject (Spotify in ban mode, mostra errore)
  401 → dispatcha auth:expired (logout automatico)
```

Non modificare questo interceptor senza capire l'interazione con `SpotifyAuthError` nel backend.

## Component Conventions

### Directory Structure

```
src/
├── components/
│   ├── cards/       → KPICard, PlaylistStatCard, TrackCard
│   ├── charts/      → componenti Recharts + ArtistNetwork (SVG) + TasteMap (scatter PCA)
│   ├── layout/      → AppLayout, Sidebar, Header
│   ├── profile/     → ObscurityGauge, GenreDNA, DecadeChart, PersonalityBadge, LifetimeStats, TasteMap
│   ├── share/       → ShareCardRenderer, ProfileShareCard
│   ├── ui/          → PeriodSelector, Skeleton, StaggerContainer
│   └── cards/       → KPICard, PlaylistStatCard, TrackCard
├── contexts/        → AuthContext
├── hooks/           → useSpotifyData, useAudioAnalysis, usePlaylistCompare
├── lib/             → api.js, constants.js, chartTheme.js
├── pages/           → lazy-loaded pages
└── styles/          → globals.css
```

### KPICard Pattern

```jsx
<KPICard
  title="Artisti"           // label in italiano
  value={42}                // numero (animato) o stringa
  suffix=""                 // opzionale: %, "brani", etc.
  trend={5.2}               // opzionale: +/- percentuale
  icon={Music}              // opzionale: icona Lucide
  delay={100}               // stagger animation (ms)
  tooltip="Info aggiuntiva" // opzionale: hover tooltip
  link="/discovery"         // opzionale: rende la card cliccabile
/>
```

- I numeri vengono animati con `useAnimatedValue` (counter da 0 al valore)
- Accent bar verticale a sinistra (3px, `bg-accent`)
- Tooltip appare on hover in basso sulla card

### PeriodSelector Pattern

```jsx
const [timeRange, setTimeRange] = useState('medium_term')

<PeriodSelector value={timeRange} onChange={setTimeRange} />
```

Usa `TIME_PERIODS` da `lib/constants.js`. Labels visibili nella UI: `1M / 6M / All`.

### Sezioni vuote

Nascondere, mai mostrare "nessun dato disponibile". Usare conditional rendering:

```jsx
{data?.rising?.length > 0 && (
  <section>
    <h3>In ascesa</h3>
    {/* ... */}
  </section>
)}
```

### Expandable Cards (PlaylistStatCard)

```jsx
<PlaylistStatCard
  playlist={playlist}
  expanded={expandedId === playlist.id}
  onExpand={() => setExpandedId(prev => prev === playlist.id ? null : playlist.id)}
/>
```

Lazy-load dei track data solo quando espanso.

## Styling System

### Tailwind Config

Palette Spotify-dark con accent indigo:

| Token | Valore | Uso |
|-------|--------|-----|
| `background` | `#121212` | Body background |
| `surface` | `#181818` | Card, sidebar |
| `surface-hover` | `#282828` | Card hover, bordi |
| `accent` | `#6366f1` | CTA, selected, accent bar |
| `accent-hover` | `#818cf8` | Hover su accent |
| `text-primary` | `#FFFFFF` | Testo principale |
| `text-secondary` | `#b3b3b3` | Label, subtitle |
| `text-muted` | `#8a8a8a` | Hint, disabled |
| `spotify` | `#1DB954` | Solo per branding Spotify |

### Fonts

- `font-display` → Space Grotesk (titoli, numeri grandi)
- `font-body` → Inter (testo, label)

### CSS Utilities (globals.css)

- `.glow-card`: card con hover → `surface-hover`, transition 300ms
- `.gradient-text`: testo gradient indigo
- `.stagger-1` ... `.stagger-4`: animation delay 0.1s–0.4s
- `.audio-bar`: barra animata per login page

### Animations (Framer Motion + Tailwind)

**Framer Motion (primary):**
- **Page transitions**: `AnimatePresence` in `AppLayout.jsx` — enter fade+slide-up (300ms), exit fade+slide-down (150ms)
- **StaggerContainer + StaggerItem**: reusable wrappers (`components/ui/StaggerContainer.jsx`) — parent staggers children at 40ms, items fade+slide-up (300ms)
- **KPICard whileInView**: scroll-driven fade-in, `viewport={{ once: true, margin: '-40px' }}`, delay from `delay` prop (ms→s)
- **Sidebar mobile**: `AnimatePresence` + `motion.aside` (x: -240→0) + `motion.div` overlay (opacity fade)

**Skeleton loaders** (`components/ui/Skeleton.jsx`):
- `SkeletonKPICard`, `SkeletonTrackRow`, `SkeletonCard`, `SkeletonGrid` — replace LoadingSpinner in pages

**Tailwind (legacy/supplementary):**
- `animate-fade-in`: opacity 0→1, 0.5s (non-motion contexts)
- `animate-pulse-glow`: box-shadow indigo pulsante
- `animate-float`: translate Y oscillante (6s)

## Testo e Localizzazione

- Tutto il testo UI in **italiano**
- Period labels: `1M / 6M / All` nei bottoni UI
- "Cluster" → **"Cerchia"** ovunque
- Messaggi di errore in italiano
- Non usare il verde Spotify (#1DB954) come accent — quello è solo per il logo/branding
