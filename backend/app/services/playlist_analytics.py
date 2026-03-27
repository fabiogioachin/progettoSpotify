"""Analisi approfondita delle playlist dell'utente."""

import logging
from datetime import datetime

from app.services.spotify_client import SpotifyClient
from app.utils.rate_limiter import (
    SpotifyAuthError,
    gather_in_chunks,
    retry_with_backoff,
)

logger = logging.getLogger(__name__)


async def analyze_playlists(client: SpotifyClient) -> dict:
    """Analisi completa delle playlist: personalità, overlap, freshness."""

    # 1. Fetch all playlists (paginated)
    all_playlists = []
    offset = 0
    while True:
        data = await retry_with_backoff(client.get_playlists, limit=50, offset=offset)
        items = data.get("items", [])
        all_playlists.extend(items)
        if len(items) < 50:
            break
        offset += 50

    if not all_playlists:
        return _empty_result()

    # 2. Summary stats
    public_count = sum(1 for p in all_playlists if p.get("public"))
    private_count = len(all_playlists) - public_count
    collaborative_count = sum(1 for p in all_playlists if p.get("collaborative"))

    # Dev mode: /me/playlists may return tracks.total=0. Fetch real counts.
    raw_sizes = {p["id"]: p.get("tracks", {}).get("total", 0) for p in all_playlists}
    zero_count_pids = [pid for pid, sz in raw_sizes.items() if sz == 0]
    if zero_count_pids:
        # Fetch real count for playlists with total=0 (limit=1, read total only)
        async def _fetch_count(pid: str) -> tuple[str, int]:
            try:
                data = await retry_with_backoff(
                    client.get_playlist_items, pid, limit=1, offset=0
                )
                return pid, data.get("total", 0)
            except SpotifyAuthError:
                raise
            except Exception:
                return pid, 0

        count_results = await gather_in_chunks(
            [_fetch_count(pid) for pid in zero_count_pids[:50]],
            chunk_size=5,
        )
        for r in count_results:
            if isinstance(r, SpotifyAuthError):
                raise r
            if isinstance(r, tuple):
                raw_sizes[r[0]] = r[1]

    sizes = [raw_sizes.get(p["id"], 0) for p in all_playlists]

    # 3. Analyze top 20 playlists by size (for overlap and details)
    playlists_sorted = sorted(
        all_playlists,
        key=lambda p: raw_sizes.get(p["id"], 0),
        reverse=True,
    )
    playlists_to_analyze = playlists_sorted[:50]

    playlist_tracks = {}
    playlist_details = []

    async def fetch_playlist_data(playlist):
        pid = playlist["id"]
        track_ids = []
        artists = set()
        release_dates = []
        added_dates = []
        try:
            # Use /items endpoint (Feb 2026: /tracks renamed to /items)
            offset = 0
            while True:
                data = await retry_with_backoff(
                    client.get_playlist_items, pid, limit=50, offset=offset
                )
                items = data.get("items", [])
                for item in items:
                    # Feb 2026: field renamed from "track" to "item"
                    track = item.get("item") or item.get("track")
                    if not track or not track.get("id"):
                        continue
                    track_ids.append(track["id"])
                    for a in track.get("artists", []):
                        if a.get("id"):
                            artists.add(a["id"])
                    album = track.get("album", {})
                    rd = album.get("release_date")
                    if rd:
                        release_dates.append(rd)
                    added_at = item.get("added_at")
                    if added_at:
                        added_dates.append(added_at)
                if not data.get("next") or len(items) < 50:
                    break
                offset += 50
        except SpotifyAuthError:
            raise
        except Exception as exc:
            logger.warning("Errore fetch playlist %s: %s", pid, exc)
        return pid, track_ids, artists, release_dates, added_dates

    tasks = [fetch_playlist_data(p) for p in playlists_to_analyze]
    results = await gather_in_chunks(tasks, chunk_size=4)

    for r in results:
        if isinstance(r, SpotifyAuthError):
            raise r
        if isinstance(r, Exception):
            logger.warning("Errore fetch playlist batch: %s", r)
            continue
        pid, track_ids, artists, release_dates, added_dates = r
        playlist_tracks[pid] = set(track_ids)

        artist_concentration = round(min(len(artists) / max(len(track_ids), 1), 1.0), 2)
        freshness = _compute_freshness(release_dates)
        staleness = _compute_staleness(added_dates)

        p_info = next((p for p in all_playlists if p["id"] == pid), {})
        images = p_info.get("images", [])
        playlist_details.append(
            {
                "id": pid,
                "name": p_info.get("name", ""),
                "image": images[0]["url"] if images else None,
                "track_count": len(track_ids),
                "unique_artists": len(artists),
                "artist_concentration": artist_concentration,
                "freshness_year": freshness,
                "staleness_days": staleness,
                "is_public": p_info.get("public", False),
                "is_collaborative": p_info.get("collaborative", False),
            }
        )

    # 4. Update sizes with actual fetched track counts
    # sizes from /me/playlists may be 0 in dev mode; replace with real counts
    actual_counts = {d["id"]: d["track_count"] for d in playlist_details}
    sizes = [
        actual_counts.get(p["id"], p.get("tracks", {}).get("total", 0))
        for p in all_playlists
    ]

    # 5. Overlap matrix (Jaccard index)
    overlap_matrix = _compute_overlap_matrix(playlist_details, playlist_tracks)

    # 6. Size distribution histogram
    size_distribution = _compute_size_histogram(sizes)

    return {
        "summary": {
            "total_playlists": len(all_playlists),
            "public_count": public_count,
            "private_count": private_count,
            "collaborative_count": collaborative_count,
            "avg_size": round(sum(sizes) / len(sizes), 1) if sizes else 0,
            "total_tracks": sum(sizes),
        },
        "size_distribution": size_distribution,
        "playlists": playlist_details,
        "overlap_matrix": overlap_matrix,
    }


def _compute_freshness(release_dates: list) -> float:
    """Calcola l'anno medio delle release date."""
    years = []
    for rd in release_dates:
        try:
            year = int(rd[:4])
            if 1900 <= year <= 2030:
                years.append(year)
        except (ValueError, IndexError):
            continue
    return round(sum(years) / len(years), 1) if years else 0


def _compute_staleness(added_dates: list) -> int:
    """Calcola i giorni dall'ultima traccia aggiunta."""
    if not added_dates:
        return -1
    try:
        dates = []
        for d in added_dates:
            dt = datetime.fromisoformat(d.replace("Z", "+00:00"))
            dates.append(dt)
        most_recent = max(dates)
        delta = datetime.now(most_recent.tzinfo) - most_recent
        return delta.days
    except Exception:
        return -1


def _compute_overlap_matrix(playlist_details: list, playlist_tracks: dict) -> dict:
    """Calcola la matrice di overlap (Jaccard index) tra playlist."""
    ids = [p["id"] for p in playlist_details]
    names = {p["id"]: p["name"] for p in playlist_details}
    matrix = []

    for i, pid_a in enumerate(ids):
        row = []
        tracks_a = playlist_tracks.get(pid_a, set())
        for j, pid_b in enumerate(ids):
            if i == j:
                row.append(100.0)
            else:
                tracks_b = playlist_tracks.get(pid_b, set())
                union = tracks_a | tracks_b
                intersection = tracks_a & tracks_b
                jaccard = round(len(intersection) / len(union) * 100, 1) if union else 0
                row.append(jaccard)
        matrix.append(row)

    return {
        "labels": [names.get(pid, pid) for pid in ids],
        "matrix": matrix,
    }


def _compute_size_histogram(sizes: list) -> list:
    """Raggruppa le dimensioni delle playlist in bucket."""
    buckets = [
        ("1-10", 1, 10),
        ("11-30", 11, 30),
        ("31-50", 31, 50),
        ("51-100", 51, 100),
        ("101-200", 101, 200),
        ("200+", 201, 99999),
    ]
    result = []
    for label, low, high in buckets:
        count = sum(1 for s in sizes if low <= s <= high)
        result.append({"range": label, "count": count})
    # Include empty playlists
    empty = sum(1 for s in sizes if s == 0)
    if empty > 0:
        result.insert(0, {"range": "Vuote", "count": empty})
    return result


def _empty_result():
    return {
        "summary": {
            "total_playlists": 0,
            "public_count": 0,
            "private_count": 0,
            "collaborative_count": 0,
            "avg_size": 0,
            "total_tracks": 0,
        },
        "size_distribution": [],
        "playlists": [],
        "overlap_matrix": {"labels": [], "matrix": []},
    }
