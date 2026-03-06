---
name: chart-dashboard
description: Reference patterns for dark-themed analytics dashboards using Recharts, custom SVG, and Tailwind CSS. Covers chart configuration, responsive grids, data transformations, Spotify color palette, and animation patterns. Not an audit — provides patterns to follow.
---

# Chart Dashboard Skill

Reference patterns for building analytics dashboards. Optimized for dark themes, Recharts, and custom SVG visualizations.

## When to Use

- Building new dashboard pages or chart components
- Adding new visualizations (radar, heatmap, network graph)
- Reviewing chart accessibility and responsiveness
- Implementing data-driven animations

## This Skill is a Reference

Unlike audit skills, `chart-dashboard` does NOT produce findings. It provides:
- Design patterns for dark-themed charts
- Recharts configuration snippets
- Custom SVG component patterns
- Responsive grid layouts

## Design System

### Color Palette (Spotify-inspired)

```javascript
// tailwind.config.js
colors: {
  background: '#0a0a0a',     // Page background
  surface: '#141414',         // Card background
  'surface-hover': '#1a1a1a', // Card hover
  border: '#262626',          // Borders
  text: {
    primary: '#e5e5e5',       // Main text
    secondary: '#8a8a8a',     // Muted text (WCAG AA)
    muted: '#6a6a6a',         // Subtle text
  },
  accent: '#6366f1',          // Indigo accent (not Spotify green)
  spotify: '#1DB954',         // Spotify green (used sparingly)
}
```

### Chart Theme (Recharts)

```javascript
// chartTheme.js
export const CHART_COLORS = ['#6366f1', '#8b5cf6', '#a78bfa', '#c4b5fd', '#1DB954'];
export const GRID_COLOR = '#262626';
export const TOOLTIP_BG = '#1a1a1a';

export const tooltipStyle = {
  backgroundColor: TOOLTIP_BG,
  border: '1px solid #262626',
  borderRadius: '8px',
  color: '#e5e5e5',
};
```

### Key Patterns

#### 1. Responsive Chart Grid

```jsx
<div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
  <div className="bg-surface rounded-xl p-6 border border-border">
    <h3 className="text-lg font-semibold text-text-primary mb-4">Title</h3>
    <ResponsiveContainer width="100%" height={300}>
      {/* chart */}
    </ResponsiveContainer>
  </div>
</div>
```

#### 2. Custom SVG Visualizations

For complex visualizations not supported by Recharts (network graphs, force-directed layouts):
- Use raw SVG with `requestAnimationFrame` for animation
- Implement in a standalone component with `useRef` + `useEffect`
- Example: `ArtistNetworkGraph.jsx` — force-directed graph with BFS clustering

#### 3. Data Hook Pattern

```jsx
// useSpotifyData.js — standard data fetching hook
const { data, loading, error } = useSpotifyData('/api/endpoint');
```

All pages use this pattern. The hook handles auth errors (401 → redirect to login).

#### 4. Empty/Loading/Error States

```jsx
{loading && <LoadingSpinner />}
{error && <ErrorMessage message={error} />}
{!loading && !error && data && (
  // Render chart only when data is available
)}
```

**Rule:** Never render a chart with undefined/null data. Always guard.

#### 5. Fallback for Deprecated APIs

```jsx
{data.has_audio_features ? (
  <AudioRadarChart features={data.features} />
) : (
  <div className="text-text-secondary text-sm">
    Dati audio non disponibili per questa selezione.
  </div>
)}
```

**Rule:** Always check `has_*` flags from backend before rendering deprecated-API-dependent charts.

## Animation Patterns

- Page transitions: `animate-fade-in` CSS animation keyed on `pathname`
- Chart entry: staggered `animation-delay` on grid children
- Value counters: `useAnimatedValue` hook (animates from previous value, not from 0)
- Heatmap: multi-color gradient with stagger animation per cell

## Pages Reference (7 pages)

| Page | Key Visualizations |
|------|-------------------|
| Dashboard | KPI cards, top tracks list, genre distribution |
| Discovery | Genre clusters, popularity distribution, outliers |
| Taste Evolution | 3-period artist/track comparison, historical tops |
| Temporal | Heatmap, streak display, session stats |
| Artist Network | Force-directed SVG graph with BFS clusters |
| Playlist Analytics | Track stats, audio features radar, mood scatter |
| Playlist Compare | Side-by-side playlist comparison |

## Verification Checklist

After building or modifying dashboard components:
1. Chart renders correctly with real data (not mocked)
2. Empty state displays when no data available
3. Loading spinner shows during fetch
4. Error message displays on API failure
5. Responsive: works on mobile (< 768px) and desktop
6. Dark theme: no white backgrounds or low-contrast text
7. Italian labels: all user-facing text in Italian
