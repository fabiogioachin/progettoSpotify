---
name: data-integrity-check
description: >
  Verify no hardcoded fake data, proper fallback flags, API response
  transparency. Ensures all displayed data comes from real API calls.
  Project-specific skill.
---

# Data Integrity Check

Single-agent audit ensuring all displayed data is real, fallbacks are transparent, and no hardcoded values masquerade as API data.

## Agent

| Agent | Focus |
|-------|-------|
| **Data Analyst** | Hardcoded defaults, fallback transparency, API response completeness |

## Rules

### No Fake Defaults
- Missing numeric data MUST default to `0` or `None` — NEVER to a plausible value
- Example of BAD: `duration_ms: int = 180000` (looks like a real 3-minute track)
- Example of GOOD: `duration_ms: int = 0` or `duration_ms: int | None = None`

### Fallback Transparency
- Every backend endpoint that uses deprecated APIs MUST return a `has_*` or `*_source` flag
- Frontend MUST check these flags and show alternative UI when data is unavailable
- The alternative UI MUST explain WHY data is missing (not just be empty)

### API Response Completeness
- `asyncio.gather` results with `_safe_fetch` may return partial data — UI must handle this
- Track/artist objects from Spotify may have null fields (preview_url, images) — guard against it
- Recently played is capped at 50 items — UI should communicate this limit

## Scan Targets

```bash
# Look for suspicious numeric defaults
grep -rn "default=\d\{4,\}" backend/app/

# Look for hardcoded plausible values
grep -rn "180000\|240000\|0\.5\|0\.7\|0\.8" backend/app/services/ backend/app/models/

# Look for missing has_* flags
grep -rn "has_audio\|has_features\|_source" backend/app/routers/
```

## Checklist

- [ ] No models/schemas with defaults that look like real measurements
- [ ] Every deprecated-API-dependent endpoint has a transparency flag
- [ ] Frontend checks transparency flags before rendering deprecated-data charts
- [ ] Empty/partial API responses show informative UI (not blank cards)
- [ ] DB-accumulated data (RecentPlay) shows actual count vs API limit
- [ ] Historical tops ("Your Top Songs 20XX") clearly labeled as playlist-sourced

## Key Files
- `backend/app/models/*.py` — check field defaults
- `backend/app/schemas.py` — check response model defaults
- `backend/app/services/*.py` — check return value defaults
- `backend/app/routers/analytics.py` — `has_audio_features` flag
