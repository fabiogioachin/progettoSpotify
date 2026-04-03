"""MusicBrainz API client for artist genre/tag lookup as Spotify fallback.

Lightweight async client that searches MusicBrainz for artist genres/tags.
Completely independent — no imports from the project except stdlib + httpx.

MusicBrainz rate limit: max 1 request per second (enforced via semaphore + sleep).
Returns 503 on rate limit violation (not 429).
"""

import asyncio
import logging
import time

import httpx

logger = logging.getLogger(__name__)

MUSICBRAINZ_API = "https://musicbrainz.org/ws/2"
USER_AGENT = "WrapApp/1.0 (spotify-listening-intelligence)"

# ---------------------------------------------------------------------------
# Tags that are NOT music genres — filtered out from MusicBrainz results.
# These cause false genre-similarity edges (e.g. Einaudi + Sfera sharing "italian").
# ---------------------------------------------------------------------------
_NON_GENRE_TAGS: frozenset[str] = frozenset(
    {
        # Nationality / language / geography
        "italian",
        "english",
        "american",
        "usa",
        "us",
        "french",
        "german",
        "spanish",
        "brazilian",
        "japanese",
        "korean",
        "swedish",
        "norwegian",
        "canadian",
        "uk",
        "british",
        "australian",
        "african",
        "latin",
        "russian",
        "polish",
        "dutch",
        "portuguese",
        "chinese",
        "mexican",
        "colombian",
        "argentinian",
        "irish",
        "scottish",
        "finnish",
        "danish",
        "belgian",
        "austrian",
        "swiss",
        "jamaican",
        "cuban",
        "puerto rican",
        "dominican",
        "chilean",
        "peruvian",
        "venezuelan",
        "ecuadorian",
        "uruguayan",
        "paraguayan",
        "bolivian",
        "icelandic",
        "greek",
        "turkish",
        "indian",
        "thai",
        "indonesian",
        "filipino",
        "malaysian",
        "vietnamese",
        "new zealand",
        "south african",
        "nigerian",
        "ghanaian",
        "kenyan",
        "tanzanian",
        "ugandan",
        "ethiopian",
        "senegalese",
        "ivorian",
        "congolese",
        "cameroonian",
        "malian",
        "englisch",
        "italiano",
        "francais",
        "deutsch",
        "espanol",
        # Decades / years
        "2020s",
        "2010s",
        "2000s",
        "1990s",
        "1980s",
        "1970s",
        "1960s",
        "1950s",
        "00s",
        "10s",
        "20s",
        "70s",
        "80s",
        "90s",
        # Meta / quality tags
        "fixme",
        "seen live",
        "favorite",
        "favourites",
        "good",
        "love",
        "under 2000 listeners",
        "all",
        "check",
        # Role descriptors (not genres)
        "voice actor",
        "pianist",
        "composer",
        "singer",
        "rapper",
        "dj",
        "producer",
        "singer-songwriter",
        "songwriter",
        "musician",
        "vocalist",
        "instrumentalist",
        "band",
        "group",
        "duo",
        "trio",
        "solo",
        "female",
        "male",
        # Personal names erroneously used as tags
        "lil baby",
        "travis scott",
        "50 cent",
        # Junk / meaningless
        "maggot brain",
        "death by murder",
        "lesbian",
        "relic inn",
        "noyz narcos & fritz da cat",
        "hip hop rnb and dance hall",
        "rap us",
    }
)

# MusicBrainz requires max 1 request/second — enforced globally
_mb_semaphore = asyncio.Semaphore(1)
_last_call_time: float = 0

# Minimum interval between requests (slightly over 1s for safety)
_MIN_INTERVAL: float = 1.1


def _is_genre_tag(tag: str) -> bool:
    """Return True if the tag is a valid music genre (not in blocklist)."""
    return tag not in _NON_GENRE_TAGS


def filter_non_genre_tags(genres: list[str]) -> list[str]:
    """Remove non-genre tags from a list of genre strings.

    Exported so other modules (e.g. warmup) can re-filter already-stored data.
    """
    return [g for g in genres if _is_genre_tag(g)]


async def _wait_rate_limit() -> None:
    """Enforce MusicBrainz 1 req/s rate limit."""
    global _last_call_time
    now = time.monotonic()
    elapsed = now - _last_call_time
    if elapsed < _MIN_INTERVAL:
        await asyncio.sleep(_MIN_INTERVAL - elapsed)


async def _mark_call() -> None:
    """Record the timestamp of the last API call."""
    global _last_call_time
    _last_call_time = time.monotonic()


def _pick_best_match(candidates: list[dict], query_name: str) -> dict | None:
    """Pick the best MusicBrainz artist match from search candidates.

    Strategy:
    1. Only consider candidates with score >= 85
    2. Sort by score descending
    3. Among candidates within 10 points of the top score, prefer the one
       whose name exactly matches the query (case-insensitive). This prevents
       e.g. "Eddie Meduza" (score=100) from beating "MEDUZA" (score=91)
       when searching for "MEDUZA".
    """
    if not candidates:
        return None

    viable = [a for a in candidates if a.get("score", 0) >= 85]
    if not viable:
        return None

    viable.sort(key=lambda a: a.get("score", 0), reverse=True)
    top_score = viable[0].get("score", 0)
    query_lower = query_name.lower().strip()

    # Among candidates within 10 points of the top, prefer exact name match
    best = viable[0]
    for a in viable:
        if a.get("score", 0) < top_score - 10:
            break  # too far below top score
        candidate_name = a.get("name", "").lower().strip()
        if candidate_name == query_lower:
            best = a
            break

    return best


async def search_artist_genres(artist_name: str) -> list[str]:
    """Search MusicBrainz for an artist by name and return genre/tag strings.

    Two-step lookup:
    1. Search artist by name, pick best match via _pick_best_match()
    2. If search result has no tags, lookup by MBID for genres + tags

    Returns a list of genre/tag strings (max 10). Empty list if not found
    or on any error. Never raises — all errors are logged and swallowed.
    """
    if not artist_name or not artist_name.strip():
        return []

    async with _mb_semaphore:
        try:
            async with httpx.AsyncClient(timeout=10.0) as http:
                # --- Step 1: Search for artist by name ---
                await _wait_rate_limit()

                resp = await http.get(
                    f"{MUSICBRAINZ_API}/artist",
                    params={
                        "query": f'artist:"{artist_name}"',
                        "limit": 5,
                        "fmt": "json",
                    },
                    headers={
                        "User-Agent": USER_AGENT,
                        "Accept": "application/json",
                    },
                )
                await _mark_call()

                if resp.status_code == 503:
                    logger.warning("MusicBrainz rate limited (503)")
                    return []
                resp.raise_for_status()

                data = resp.json()
                artists = data.get("artists", [])
                if not artists:
                    return []

                best = _pick_best_match(artists, artist_name)

                if not best:
                    return []

                # Extract tags from search result
                genres: list[str] = []
                for tag in best.get("tags", []):
                    name = tag.get("name", "").strip().lower()
                    if name and name not in genres and _is_genre_tag(name):
                        genres.append(name)

                if genres:
                    return genres[:10]

                # --- Step 2: Lookup by MBID for detailed genres + tags ---
                mbid = best.get("id")
                if not mbid:
                    return []

                await _wait_rate_limit()

                resp2 = await http.get(
                    f"{MUSICBRAINZ_API}/artist/{mbid}",
                    params={"inc": "genres tags", "fmt": "json"},
                    headers={
                        "User-Agent": USER_AGENT,
                        "Accept": "application/json",
                    },
                )
                await _mark_call()

                if resp2.status_code == 503:
                    return []
                resp2.raise_for_status()

                detail = resp2.json()

                # Prefer genres (curated) over tags (community-driven)
                for g in detail.get("genres", []):
                    name = g.get("name", "").strip().lower()
                    if name and name not in genres and _is_genre_tag(name):
                        genres.append(name)

                for t in detail.get("tags", []):
                    name = t.get("name", "").strip().lower()
                    count = t.get("count", 0)
                    if (
                        name
                        and name not in genres
                        and count > 0
                        and _is_genre_tag(name)
                    ):
                        genres.append(name)

                return genres[:10]

        except httpx.HTTPStatusError as exc:
            logger.warning(
                "MusicBrainz HTTP error for '%s': %s %s",
                artist_name,
                exc.response.status_code,
                exc.response.reason_phrase,
            )
            await _mark_call()
            return []
        except Exception as exc:
            logger.warning("MusicBrainz lookup failed for '%s': %s", artist_name, exc)
            await _mark_call()
            return []
