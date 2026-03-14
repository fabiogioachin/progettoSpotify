"""Utility pure-compute per matching fuzzy di generi musicali.

Modulo pure-compute: NON importa SpotifyClient, NON fa chiamate HTTP.
Lavora esclusivamente su dati locali (stringhe di generi).
"""

from collections import Counter


def normalize_genre(genre: str) -> str:
    """Normalizza un genere: lowercase, strip, collassa trattini/spazi multipli.

    Esempio: "Indie-Rock" -> "indie rock", "  hip  hop " -> "hip hop"
    """
    result = genre.lower().strip()
    result = result.replace("-", " ")
    # Collapse multiple spaces
    result = " ".join(result.split())
    return result


def genres_are_related(a: str, b: str) -> bool:
    """Determina se due generi sono correlati.

    True se:
    - Match esatto dopo normalizzazione
    - Uno e' sottostringa dell'altro ("rock" in "hard rock")
    - Overlap di token >= soglia (1 token condiviso per generi corti, 2+ per generi lunghi)
    """
    norm_a = normalize_genre(a)
    norm_b = normalize_genre(b)

    if not norm_a or not norm_b:
        return False

    # Exact match
    if norm_a == norm_b:
        return True

    # Substring match
    if norm_a in norm_b or norm_b in norm_a:
        return True

    # Token overlap
    tokens_a = set(norm_a.split())
    tokens_b = set(norm_b.split())
    shared_tokens = tokens_a & tokens_b

    if not shared_tokens:
        return False

    # For short genres (1-2 tokens each), 1 shared token is enough
    # For longer genres (3+ tokens in either), require 2+ shared tokens
    max_tokens = max(len(tokens_a), len(tokens_b))
    if max_tokens >= 3:
        return len(shared_tokens) >= 2
    return len(shared_tokens) >= 1


def compute_genre_similarity(genres_a: list, genres_b: list) -> float:
    """Calcola similarita' 0.0-1.0 tra due insiemi di generi.

    Per ogni genere in A, trova il miglior match in B:
    - Match esatto: 1.0
    - Sottostringa: 0.7
    - Overlap token: 0.4
    Normalizzato per max(len(a), len(b)).

    Restituisce 0.0 per input vuoti.
    """
    if not genres_a or not genres_b:
        return 0.0

    total_score = 0.0

    for ga in genres_a:
        norm_a = normalize_genre(ga)
        if not norm_a:
            continue

        best_score = 0.0
        for gb in genres_b:
            norm_b = normalize_genre(gb)
            if not norm_b:
                continue

            # Exact match
            if norm_a == norm_b:
                best_score = 1.0
                break  # Can't do better

            # Substring match
            if norm_a in norm_b or norm_b in norm_a:
                best_score = max(best_score, 0.7)
                continue

            # Token overlap
            tokens_a = set(norm_a.split())
            tokens_b = set(norm_b.split())
            shared = tokens_a & tokens_b
            if shared:
                max_tokens = max(len(tokens_a), len(tokens_b))
                if max_tokens >= 3 and len(shared) >= 2:
                    best_score = max(best_score, 0.4)
                elif max_tokens < 3 and len(shared) >= 1:
                    best_score = max(best_score, 0.4)

        total_score += best_score

    denominator = max(len(genres_a), len(genres_b))
    return round(total_score / denominator, 4) if denominator > 0 else 0.0


def build_genre_vocabulary(all_genres: list, max_features: int = 20) -> list[str]:
    """Restituisce i top N generi normalizzati per one-hot encoding.

    Args:
        all_genres: lista piatta di generi (anche con duplicati)
        max_features: numero massimo di generi da restituire

    Returns:
        Lista dei generi normalizzati piu' frequenti, ordinati per frequenza decrescente.
    """
    if not all_genres:
        return []

    normalized = [normalize_genre(g) for g in all_genres]
    normalized = [g for g in normalized if g]  # Remove empty strings

    counter = Counter(normalized)
    return [genre for genre, _ in counter.most_common(max_features)]
