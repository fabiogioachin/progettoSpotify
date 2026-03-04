---
name: frontend-component-review
description: >
  Review React components: hooks usage, Tailwind patterns, Italian localization
  consistency, custom SVG visualizations, accessibility.
  Project-specific skill.
---

# Frontend Component Review

Targeted review of React frontend components. Checks hook patterns, Tailwind usage, localization, and custom SVG quality.

## Agents

| Agent | Focus |
|-------|-------|
| **Component Quality** | Hook dependencies, memo usage, key props, conditional rendering guards, data null checks |
| **Design Consistency** | Tailwind classes, CSS variables, Spotify palette, dark theme compliance, responsive breakpoints |

## Checklist

### React Patterns
- [ ] `useSpotifyData` hook used consistently (not raw fetch)
- [ ] Loading/error/empty states handled in every page
- [ ] `useAnimatedValue` animates from previous value (not from 0)
- [ ] Chart components guard against undefined/null data
- [ ] Keys on list items are stable (not array index for dynamic lists)

### Tailwind / Design
- [ ] No hardcoded colors — use Tailwind theme tokens (`bg-surface`, `text-text-primary`)
- [ ] No white backgrounds (dark theme only)
- [ ] `GRID_COLOR` constant used instead of hardcoded border colors in charts
- [ ] Consistent padding: `py-8` for page content
- [ ] Responsive: `grid-cols-1 lg:grid-cols-2` pattern for chart grids

### Italian Localization
- [ ] All user-facing text in Italian
- [ ] No English strings remaining (Tracks→Brani, Artists→Artisti, etc.)
- [ ] Error messages in Italian
- [ ] Empty state messages in Italian

### Accessibility
- [ ] `text-muted` contrast ratio meets WCAG AA (#8a8a8a on dark bg)
- [ ] `focus-visible` outline styles present
- [ ] Interactive elements have visible focus states
- [ ] SVG visualizations have aria-labels

### Custom SVG
- [ ] Force-directed graph uses `requestAnimationFrame` (not setInterval)
- [ ] SVG gradients have unique IDs (no ID collisions between chart instances)
- [ ] AudioRadar detects all-zero features and shows "dati non disponibili"

## Key Files
- `frontend/src/pages/*.jsx` — 7 page components
- `frontend/src/components/` — reusable chart and UI components
- `frontend/src/hooks/useSpotifyData.js` — data fetching hook
- `frontend/src/styles/globals.css` — CSS variables, scrollbar, glow-card
- `frontend/tailwind.config.js` — Spotify color palette
- `frontend/src/lib/chartTheme.js` — Recharts theme constants
