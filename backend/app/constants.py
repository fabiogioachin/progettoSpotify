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

TIME_RANGES = ("short_term", "medium_term", "long_term")

TIME_RANGE_LABELS = {
    "short_term": "Ultimo mese",
    "medium_term": "Ultimi 6 mesi",
    "long_term": "Sempre",
}
