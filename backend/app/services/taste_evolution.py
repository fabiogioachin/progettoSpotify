"""Analisi dell'evoluzione del gusto musicale attraverso i periodi temporali."""

import asyncio

from app.services.spotify_client import SpotifyClient
from app.utils.rate_limiter import retry_with_backoff


async def compute_taste_evolution(client: SpotifyClient) -> dict:
    """Confronta artisti e brani tra short, medium e long term."""

    # Fetch top artists + tracks for all 3 time ranges in parallel
    results = await asyncio.gather(
        retry_with_backoff(client.get_top_artists, time_range="short_term", limit=50),
        retry_with_backoff(client.get_top_artists, time_range="medium_term", limit=50),
        retry_with_backoff(client.get_top_artists, time_range="long_term", limit=50),
        retry_with_backoff(client.get_top_tracks, time_range="short_term", limit=50),
        retry_with_backoff(client.get_top_tracks, time_range="medium_term", limit=50),
        retry_with_backoff(client.get_top_tracks, time_range="long_term", limit=50),
    )

    short_artists_raw, medium_artists_raw, long_artists_raw = results[0], results[1], results[2]
    short_tracks_raw, medium_tracks_raw, long_tracks_raw = results[3], results[4], results[5]

    # Build artist dicts {id: artist_data}
    def build_artist_map(data):
        return {a["id"]: a for a in data.get("items", [])}

    short_artists = build_artist_map(short_artists_raw)
    medium_artists = build_artist_map(medium_artists_raw)
    long_artists = build_artist_map(long_artists_raw)

    short_ids = set(short_artists.keys())
    medium_ids = set(medium_artists.keys())
    long_ids = set(long_artists.keys())

    # Classifications
    rising_ids = short_ids - long_ids
    falling_ids = long_ids - short_ids
    loyal_ids = short_ids & medium_ids & long_ids

    def format_artist(source_map, aid):
        a = source_map.get(aid, {})
        images = a.get("images", [])
        return {
            "id": aid,
            "name": a.get("name", ""),
            "image": images[0]["url"] if images else None,
        }

    rising = [format_artist(short_artists, aid) for aid in rising_ids]
    falling = [format_artist(long_artists, aid) for aid in falling_ids]
    loyal = [format_artist(short_artists, aid) for aid in loyal_ids]

    # Metrics
    loyalty_score = round(len(loyal_ids) / len(short_ids) * 100, 1) if short_ids else 0
    turnover_rate = round(len(short_ids - medium_ids) / len(short_ids) * 100, 1) if short_ids else 0

    # Track analysis
    def build_track_map(data):
        return {t["id"]: t for t in data.get("items", [])}

    short_tracks = build_track_map(short_tracks_raw)
    medium_tracks = build_track_map(medium_tracks_raw)
    long_tracks = build_track_map(long_tracks_raw)

    short_track_ids = set(short_tracks.keys())
    medium_track_ids = set(medium_tracks.keys())
    long_track_ids = set(long_tracks.keys())

    persistent_ids = short_track_ids & medium_track_ids & long_track_ids
    rising_track_ids = short_track_ids - long_track_ids

    def format_track(source_map, tid):
        t = source_map.get(tid, {})
        album = t.get("album", {})
        images = album.get("images", [])
        artists = t.get("artists", [])
        return {
            "id": tid,
            "name": t.get("name", ""),
            "artist": artists[0]["name"] if artists else "",
            "album_image": images[0]["url"] if images else None,
        }

    persistent_tracks = [format_track(short_tracks, tid) for tid in persistent_ids]
    rising_tracks = [format_track(short_tracks, tid) for tid in rising_track_ids]

    # Overlap distribution: how many artists appear in 1, 2, or all 3 periods
    all_artist_ids = short_ids | medium_ids | long_ids
    in_one = sum(1 for a in all_artist_ids if sum([a in short_ids, a in medium_ids, a in long_ids]) == 1)
    in_two = sum(1 for a in all_artist_ids if sum([a in short_ids, a in medium_ids, a in long_ids]) == 2)
    in_three = sum(1 for a in all_artist_ids if sum([a in short_ids, a in medium_ids, a in long_ids]) == 3)

    return {
        "artists": {
            "rising": rising[:15],
            "falling": falling[:15],
            "loyal": loyal[:15],
        },
        "tracks": {
            "persistent": persistent_tracks[:10],
            "rising": rising_tracks[:10],
        },
        "metrics": {
            "loyalty_score": loyalty_score,
            "turnover_rate": turnover_rate,
            "short_term_count": len(short_ids),
            "medium_term_count": len(medium_ids),
            "long_term_count": len(long_ids),
            "persistent_tracks_count": len(persistent_ids),
        },
        "overlap_distribution": [
            {"label": "1 periodo", "count": in_one},
            {"label": "2 periodi", "count": in_two},
            {"label": "3 periodi", "count": in_three},
        ],
    }
