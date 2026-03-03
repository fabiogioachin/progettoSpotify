# Lessons Learned

## Batch 1 — 4 Feature + UI/UX Spotify-Style

### What Worked
- Parallel subagents for independent backend services saved significant time
- Pure SVG force-directed graph avoided heavy d3 dependency
- BFS cluster detection was simple and effective for artist network
- asyncio.Semaphore prevented Spotify rate limiting issues
- AppLayout pattern cleanly separated nav from page content

### Gotchas
- `frontend/src/index.css` didn't exist — actual path was `frontend/src/styles/globals.css`. Always use Glob to find CSS files
- Audio Features API is deprecated — never rely on it for new features
- Spotify API only has 3 fixed time ranges — can't be extended programmatically
- Recently played hard limit is 50 items — clearly communicate this in UI

### Architecture Decisions
- Kept accent color as indigo (#6366f1) rather than Spotify green to differentiate the app
- Used CSS grid (not SVG) for heatmap — simpler, more responsive
- Used Recharts only for standard charts, custom SVG for complex visualizations
- Italian localization throughout — all UI labels, error messages, export prompts
