"""Clustering e analisi del gusto musicale con scikit-learn.

Modulo pure-compute: NON importa SpotifyClient, NON fa chiamate HTTP.
Lavora esclusivamente su dati locali (feature matrix, artist dicts).
"""

import logging
import math

import numpy as np
from sklearn.decomposition import PCA
from sklearn.ensemble import IsolationForest
from sklearn.metrics.pairwise import cosine_similarity
from sklearn.preprocessing import StandardScaler

from app.services.genre_utils import build_genre_vocabulary, genres_are_related

logger = logging.getLogger(__name__)

# Audio feature columns appended when audio_features dict is provided
_AUDIO_COLS = [
    "energy",
    "danceability",
    "valence",
    "acousticness",
    "instrumentalness",
    "speechiness",
    "liveness",
]


def build_feature_matrix(
    artists: list[dict],
    audio_features: dict | None = None,
    genre_vocab: list[str] | None = None,
) -> tuple[np.ndarray, list[str], list[str]]:
    """Costruisce la matrice di feature per clustering/PCA.

    Args:
        artists: lista di dict con id, name, genres, popularity, followers.
        audio_features: opzionale, {artist_id: {energy, danceability, ...}}.
        genre_vocab: opzionale, vocabolario generi. Se None viene calcolato.

    Returns:
        (matrix, artist_ids, feature_names) dove matrix e' scalata con StandardScaler.
        Shape: (n_artists, 22) senza audio, (n_artists, 29) con audio.
    """
    if not artists:
        return np.empty((0, 0)), [], []

    # Build genre vocabulary if not provided
    if genre_vocab is None:
        all_genres = []
        for a in artists:
            all_genres.extend(a.get("genres", []))
        genre_vocab = build_genre_vocabulary(all_genres, max_features=20)

    # Pad or truncate to exactly 20 genre columns
    if len(genre_vocab) < 20:
        genre_vocab = genre_vocab + [""] * (20 - len(genre_vocab))
    else:
        genre_vocab = genre_vocab[:20]

    has_audio = audio_features is not None and len(audio_features) > 0

    feature_names = [f"genre_{g}" for g in genre_vocab] + [
        "popularity",
        "followers_log",
    ]
    if has_audio:
        feature_names += _AUDIO_COLS

    n_features = len(feature_names)
    n_artists = len(artists)
    matrix = np.zeros((n_artists, n_features), dtype=np.float64)
    artist_ids: list[str] = []

    for i, artist in enumerate(artists):
        aid = artist.get("id", "")
        artist_ids.append(aid)
        artist_genres = artist.get("genres", [])

        # Genre one-hot with fuzzy matching (20 cols)
        for j, vocab_genre in enumerate(genre_vocab):
            if not vocab_genre:
                continue
            for ag in artist_genres:
                if genres_are_related(ag, vocab_genre):
                    matrix[i, j] = 1.0
                    break

        # Popularity normalized 0-1
        matrix[i, 20] = artist.get("popularity", 0) / 100.0

        # Followers log-scaled
        followers = artist.get("followers", 0)
        matrix[i, 21] = math.log10(followers + 1) / 8.0

        # Audio features if available
        if has_audio and aid in audio_features:
            af = audio_features[aid]
            for k, col in enumerate(_AUDIO_COLS):
                matrix[i, 22 + k] = af.get(col, 0.0)

    # Scale features (replace NaN from zero-variance columns with 0)
    scaler = StandardScaler()
    matrix = scaler.fit_transform(matrix)
    np.nan_to_num(matrix, nan=0.0, copy=False)

    return matrix, artist_ids, feature_names


def name_clusters(labels: dict[str, int], artists: list[dict]) -> dict[int, str]:
    """Assegna nomi ai cluster basandosi sul genere dominante/distintivo (TF-IDF-like).

    Args:
        labels: {artist_id: cluster_id}
        artists: lista di dict con 'id' e 'genres'.

    Returns:
        {cluster_id: nome_cluster}
    """
    if not labels or not artists:
        return {}

    artist_map = {a["id"]: a for a in artists}
    total_artists = len(labels)

    # Count how many artists have each genre (global)
    genre_artist_count: dict[str, int] = {}
    for aid in labels:
        a = artist_map.get(aid)
        if not a:
            continue
        for g in a.get("genres", []):
            ng = g.lower().strip().replace("-", " ")
            if ng:
                genre_artist_count[ng] = genre_artist_count.get(ng, 0) + 1

    # Group artists by cluster
    clusters: dict[int, list[str]] = {}
    for aid, cid in labels.items():
        clusters.setdefault(cid, []).append(aid)

    result: dict[int, str] = {}

    for cid, aids in clusters.items():
        # Collect all genres in this cluster
        cluster_genres: list[str] = []
        for aid in aids:
            a = artist_map.get(aid)
            if not a:
                continue
            for g in a.get("genres", []):
                ng = g.lower().strip().replace("-", " ")
                if ng:
                    cluster_genres.append(ng)

        if not cluster_genres:
            # Fallback: use the most popular artist's name in this cluster
            cluster_artists = [
                artist_map.get(aid) for aid in aids if artist_map.get(aid)
            ]
            if cluster_artists:
                best_artist = max(cluster_artists, key=lambda a: a.get("popularity", 0))
                result[cid] = (
                    f"Cerchia di {best_artist.get('name', f'Cerchia {cid + 1}')}"
                )
            else:
                result[cid] = f"Cerchia {cid + 1}"
            continue

        total_cluster_genres = len(cluster_genres)
        genre_freq: dict[str, int] = {}
        for g in cluster_genres:
            genre_freq[g] = genre_freq.get(g, 0) + 1

        # TF-IDF-like score
        best_genre = None
        best_score = -1.0
        for genre, freq in genre_freq.items():
            tf = freq / total_cluster_genres
            idf = math.log(total_artists / (genre_artist_count.get(genre, 0) + 1))
            score = tf * idf
            if score > best_score:
                best_score = score
                best_genre = genre

        if best_genre:
            result[cid] = best_genre.replace("-", " ").title()
        else:
            result[cid] = f"Cerchia {cid + 1}"

    return result


def rank_within_cluster(
    labels: dict[str, int],
    artists: list[dict],
    pagerank: dict[str, float],
) -> dict[int, list[dict]]:
    """Classifica artisti in ogni cluster per punteggio composito.

    Score = 40% PageRank (normalizzato) + 30% popularity/100 + 30% genre_diversity/5

    Returns:
        {cluster_id: [{id, name, image, score, rank}, ...]}
    """
    if not labels or not artists:
        return {}

    artist_map = {a["id"]: a for a in artists}

    # Group by cluster
    clusters: dict[int, list[str]] = {}
    for aid, cid in labels.items():
        clusters.setdefault(cid, []).append(aid)

    result: dict[int, list[dict]] = {}

    for cid, aids in clusters.items():
        # Normalize pagerank within cluster to 0-1
        pr_values = [pagerank.get(aid, 0.0) for aid in aids]
        pr_min = min(pr_values)
        pr_max = max(pr_values)
        pr_range = pr_max - pr_min

        ranked: list[dict] = []
        for aid in aids:
            a = artist_map.get(aid, {})
            pr_raw = pagerank.get(aid, 0.0)
            pr_norm = (pr_raw - pr_min) / pr_range if pr_range > 0 else 0.0

            popularity = a.get("popularity", 0) / 100.0
            genre_diversity = min(len(a.get("genres", [])) / 5.0, 1.0)

            score = 0.4 * pr_norm + 0.3 * popularity + 0.3 * genre_diversity

            ranked.append(
                {
                    "id": aid,
                    "name": a.get("name", ""),
                    "image": a.get("image", None),
                    "score": round(score, 4),
                    "rank": 0,  # placeholder, set after sort
                }
            )

        # Sort descending by score
        ranked.sort(key=lambda x: x["score"], reverse=True)
        for idx, item in enumerate(ranked):
            item["rank"] = idx + 1

        result[cid] = ranked

    return result


def compute_taste_pca(
    matrix: np.ndarray,
    ids: list[str],
    n_components: int = 2,
) -> dict:
    """Proiezione PCA 2D per la visualizzazione TasteMap.

    Returns:
        {
            "points": [{id, x, y}, ...],
            "variance_explained": [float, float],
            "feature_mode": "audio" | "genre_popularity" | "insufficient"
        }
    """
    # Edge case: not enough data
    if matrix.shape[0] < 3:
        return {
            "points": [],
            "variance_explained": [0.0, 0.0],
            "feature_mode": "insufficient",
        }

    # Guard: if all features have zero variance (identical rows after scaling),
    # PCA produces NaN in explained_variance_ratio_. Skip PCA and return
    # zero coordinates instead — there's no meaningful variation to project.
    col_variance = np.var(matrix, axis=0)
    if np.all(col_variance < 1e-10):
        logger.info(
            "TasteMap: zero-variance matrix (%d rows), skipping PCA", matrix.shape[0]
        )
        points = [{"id": aid, "x": 0.0, "y": 0.0} for aid in ids]
        return {
            "points": points,
            "variance_explained": [0.0] * n_components,
            "feature_mode": "genre_popularity",
        }

    actual_components = min(n_components, matrix.shape[0], matrix.shape[1])
    pca = PCA(n_components=actual_components)
    projected = pca.fit_transform(matrix)

    # Sanitize any NaN/inf that may slip through numerical edge cases
    projected = np.nan_to_num(projected, nan=0.0, posinf=0.0, neginf=0.0)

    variance = pca.explained_variance_ratio_.tolist()
    # Sanitize variance values
    variance = [0.0 if (math.isnan(v) or math.isinf(v)) else v for v in variance]
    # Pad to n_components if needed
    while len(variance) < n_components:
        variance.append(0.0)

    # Determine feature mode
    if sum(variance) < 0.30:
        feature_mode = "insufficient"
    elif matrix.shape[1] > 22:
        feature_mode = "audio"
    else:
        feature_mode = "genre_popularity"

    points = []
    for i, aid in enumerate(ids):
        point = {"id": aid}
        x = float(projected[i, 0]) if actual_components >= 1 else 0.0
        y = float(projected[i, 1]) if actual_components >= 2 else 0.0
        point["x"] = 0.0 if (math.isnan(x) or math.isinf(x)) else x
        point["y"] = 0.0 if (math.isnan(y) or math.isinf(y)) else y
        points.append(point)

    return {
        "points": points,
        "variance_explained": variance[:n_components],
        "feature_mode": feature_mode,
    }


def compute_cosine_similarities(
    matrix: np.ndarray,
    ids: list[str],
) -> dict[str, float]:
    """Similarita' coseno tra ogni artista e il centroide (vettore medio).

    Returns:
        {artist_id: similarity_score (0-100, arrotondato)}
    """
    if matrix.shape[0] == 0:
        return {}

    centroid = matrix.mean(axis=0, keepdims=True)  # (1, n_features)
    similarities = cosine_similarity(matrix, centroid).flatten()  # (n_artists,)

    # Scale to 0-100
    result: dict[str, float] = {}
    for i, aid in enumerate(ids):
        # cosine_similarity returns values in [-1, 1]; scale to [0, 100]
        score = (similarities[i] + 1) / 2 * 100
        result[aid] = round(score)

    return result


def detect_outliers_isolation_forest(
    matrix: np.ndarray,
    ids: list[str],
    contamination: float = 0.1,
) -> list[str]:
    """Rileva artisti outlier con Isolation Forest.

    Returns:
        Lista di artist ID classificati come outlier.
    """
    if matrix.shape[0] < 5:
        return []

    clf = IsolationForest(contamination=contamination, random_state=42)
    predictions = clf.fit_predict(matrix)

    return [aid for aid, pred in zip(ids, predictions) if pred == -1]
