"""Costanti condivise del progetto."""

FEATURE_KEYS = [
    "danceability",
    "energy",
    "valence",
    "acousticness",
    "instrumentalness",
    "liveness",
    "speechiness",
]

# Max number of unique artists to fetch for genre distribution.
# Balances API call budget vs genre coverage (1 call per artist).
# Trends endpoint (dashboard's heaviest) uses a lower cap to stay within ~30-call budget.
ARTIST_GENRE_CAP_TRENDS = 20
# Playlist comparison uses the full cap (dedicated endpoint, less frequent).
ARTIST_GENRE_CAP_PLAYLIST = 50
