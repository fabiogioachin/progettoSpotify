"""Servizio per recuperare storico annuale dalle playlist 'Your Top Songs'."""

import asyncio
import re

from app.utils.rate_limiter import retry_with_backoff


async def get_historical_top_songs(client) -> dict:
    """Cerca playlist 'Your Top Songs YYYY' e ne estrae i brani."""
    # 1. Fetch all playlists (paginated)
    all_playlists = []
    offset = 0
    limit = 50
    while True:
        data = await retry_with_backoff(client.get_playlists, limit=limit, offset=offset)
        items = data.get("items") or []
        all_playlists.extend(items)
        if not data.get("next") or len(items) < limit:
            break
        offset += limit
        if offset > 400:  # safety cap
            break

    # 2. Filter for "Your Top Songs YYYY" pattern
    pattern = re.compile(r"Your Top Songs 20(\d{2})", re.IGNORECASE)
    matched = []
    for pl in all_playlists:
        name = pl.get("name", "")
        m = pattern.search(name)
        if m:
            year = int("20" + m.group(1))
            matched.append({
                "year": year,
                "playlist_id": pl["id"],
                "playlist_name": name,
                "total_tracks": pl.get("tracks", {}).get("total", 0),
                "image": (pl.get("images") or [{}])[0].get("url"),
            })

    if not matched:
        return {"years": [], "total_years": 0}

    # Sort by year ascending
    matched.sort(key=lambda x: x["year"])

    # 3. Fetch tracks for each playlist (sequential to respect rate limits)
    sem = asyncio.Semaphore(2)

    async def fetch_tracks(pl_info):
        async with sem:
            tracks = []
            # Use /items endpoint (Feb 2026: /tracks renamed to /items)
            offset = 0
            while True:
                data = await retry_with_backoff(
                    client.get, f"/playlists/{pl_info['playlist_id']}/items", limit=50, offset=offset
                )
                items = data.get("items", [])
                for item in items:
                    # Feb 2026: field renamed from "track" to "item"
                    t = item.get("item") or item.get("track")
                    if not t or not t.get("id"):
                        continue
                    tracks.append({
                        "name": t.get("name", ""),
                        "artist": t["artists"][0]["name"] if t.get("artists") else "",
                        "album": t.get("album", {}).get("name", ""),
                        "album_image": (t.get("album", {}).get("images") or [{}])[0].get("url"),
                    })
                if not data.get("next") or len(items) < 50:
                    break
                offset += 50
            return {
                "year": pl_info["year"],
                "playlist_name": pl_info["playlist_name"],
                "image": pl_info["image"],
                "track_count": len(tracks),
                "tracks": tracks[:100],
            }

    tasks = [fetch_tracks(pl) for pl in matched]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    years = []
    for r in results:
        if isinstance(r, Exception):
            continue
        years.append(r)

    years.sort(key=lambda x: x["year"])

    return {
        "years": years,
        "total_years": len(years),
    }
