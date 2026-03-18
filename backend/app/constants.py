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
ARTIST_GENRE_CAP = 50
