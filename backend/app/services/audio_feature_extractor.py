"""Estrazione audio features da preview MP3 via librosa.

Analizza i preview clip (~30s) dei brani Spotify per estrarre features audio
equivalenti a quelle dell'API deprecata (audio-features). L'analisi librosa
avviene in un thread pool per non bloccare il loop asyncio.
"""

import asyncio
import logging
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import httpx
import numpy as np
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.track import AudioFeatures
from app.services.audio_analyzer import get_or_fetch_features
from app.utils.rate_limiter import SpotifyAuthError

logger = logging.getLogger(__name__)


def _analyze_audio(filepath: str) -> dict:
    """Analisi sincrona con librosa (eseguita nel thread pool).

    Estrae features normalizzate 0-1 (tranne tempo in BPM).
    """
    import librosa

    y, sr = librosa.load(filepath, sr=22050, mono=True)

    if len(y) == 0:
        return {}

    # --- Energy ---
    rms = librosa.feature.rms(y=y)[0]
    energy_raw = float(np.mean(rms))
    energy = min(energy_raw / 0.3, 1.0)

    # --- Danceability (onset strength + tempo stability) ---
    onset_env = librosa.onset.onset_strength(y=y, sr=sr)
    onset_mean = float(np.mean(onset_env))
    # Tempo stability from autocorrelation of onset envelope
    ac = librosa.autocorrelate(onset_env, max_size=len(onset_env))
    if len(ac) > 1 and ac[0] > 0:
        tempo_stability = float(np.max(ac[1:]) / ac[0])
    else:
        tempo_stability = 0.0
    onset_norm = min(onset_mean / 20.0, 1.0)  # typical max ~20
    danceability = float(np.clip(onset_norm * 0.5 + tempo_stability * 0.5, 0, 1))

    # --- Valence (brightness + major/minor mode) ---
    spectral_centroid = librosa.feature.spectral_centroid(y=y, sr=sr)[0]
    centroid_mean = float(np.mean(spectral_centroid))
    brightness_norm = min(centroid_mean / (sr / 2), 1.0)
    # Major vs minor mode from chroma
    chroma = librosa.feature.chroma_cqt(y=y, sr=sr)
    # Major triads tend to have stronger C, E, G (indices 0, 4, 7)
    # Minor triads: C, Eb, G (indices 0, 3, 7)
    major_strength = float(np.mean(chroma[0]) + np.mean(chroma[4]) + np.mean(chroma[7]))
    minor_strength = float(np.mean(chroma[0]) + np.mean(chroma[3]) + np.mean(chroma[7]))
    total_mode = major_strength + minor_strength
    major_minor = (major_strength / total_mode) if total_mode > 0 else 0.5
    valence = float(np.clip(0.5 * brightness_norm + 0.5 * major_minor, 0, 1))

    # --- Acousticness (inverse of spectral centroid) ---
    acousticness = float(np.clip(1 - brightness_norm, 0, 1))

    # --- Instrumentalness (spectral flatness) ---
    spectral_flatness = librosa.feature.spectral_flatness(y=y)[0]
    instrumentalness = float(np.clip(np.mean(spectral_flatness), 0, 1))

    # --- Speechiness (ZCR + energy variance) ---
    zcr = librosa.feature.zero_crossing_rate(y=y)[0]
    zcr_norm = min(float(np.mean(zcr)) / 0.2, 1.0)  # typical speech ZCR ~0.1-0.2
    energy_var = float(np.var(rms))
    energy_var_norm = min(energy_var / 0.01, 1.0)  # normalize variance
    speechiness = float(np.clip(zcr_norm * 0.5 + energy_var_norm * 0.5, 0, 1))

    # --- Liveness (spectral flux variance / mean) ---
    spectral_flux = onset_env  # onset_strength is effectively spectral flux
    flux_mean = float(np.mean(spectral_flux))
    flux_std = float(np.std(spectral_flux))
    liveness = float(np.clip(flux_std / flux_mean, 0, 1)) if flux_mean > 0 else 0.0

    # --- Tempo ---
    tempo_val = librosa.beat.beat_track(y=y, sr=sr)[0]
    # librosa >= 0.10 returns array, extract scalar
    if hasattr(tempo_val, "__len__"):
        tempo_val = float(tempo_val[0]) if len(tempo_val) > 0 else 120.0
    else:
        tempo_val = float(tempo_val)
    tempo = float(np.clip(tempo_val, 60, 200))

    return {
        "energy": round(energy, 4),
        "danceability": round(danceability, 4),
        "valence": round(valence, 4),
        "acousticness": round(acousticness, 4),
        "instrumentalness": round(instrumentalness, 4),
        "speechiness": round(speechiness, 4),
        "liveness": round(liveness, 4),
        "tempo": round(tempo, 1),
    }


async def extract_features_from_url(preview_url: str) -> dict | None:
    """Scarica preview MP3 e analizza con librosa in un thread separato.

    Returns:
        dict con features normalizzate, oppure None in caso di errore.
    """
    if not preview_url:
        return None

    tmp_path = None
    try:
        async with httpx.AsyncClient(timeout=15.0) as http:
            resp = await http.get(preview_url)
            if resp.status_code != 200:
                logger.warning(
                    "Download preview fallito (HTTP %d): %s",
                    resp.status_code,
                    preview_url,
                )
                return None
            # Cap a 5 MB per evitare OOM su risposte anomale
            if len(resp.content) > 5 * 1024 * 1024:
                logger.warning(
                    "Preview troppo grande (%d bytes): %s",
                    len(resp.content),
                    preview_url,
                )
                return None

            # Salva in file temporaneo
            with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as tmp:
                tmp.write(resp.content)
                tmp_path = tmp.name

        # Analisi in thread pool (librosa e' CPU-bound)
        features = await asyncio.to_thread(_analyze_audio, tmp_path)
        return features if features else None

    except Exception as exc:
        logger.warning("Errore estrazione features da preview: %s", exc)
        return None
    finally:
        if tmp_path:
            try:
                Path(tmp_path).unlink(missing_ok=True)
            except OSError:
                pass


async def _save_features_to_db(db: AsyncSession, track_id: str, features: dict) -> None:
    """Salva le features estratte nel DB (upsert)."""
    try:
        result = await db.execute(
            select(AudioFeatures).where(AudioFeatures.track_spotify_id == track_id)
        )
        existing = result.scalar_one_or_none()

        if existing:
            for key, val in features.items():
                if hasattr(existing, key):
                    setattr(existing, key, val)
            existing.cached_at = datetime.now(timezone.utc)
        else:
            af = AudioFeatures(
                track_spotify_id=track_id,
                danceability=features.get("danceability"),
                energy=features.get("energy"),
                valence=features.get("valence"),
                acousticness=features.get("acousticness"),
                instrumentalness=features.get("instrumentalness"),
                liveness=features.get("liveness"),
                speechiness=features.get("speechiness"),
                tempo=features.get("tempo"),
                cached_at=datetime.now(timezone.utc),
            )
            db.add(af)

        await db.commit()
    except Exception as exc:
        logger.warning("Salvataggio features DB fallito per %s: %s", track_id, exc)
        await db.rollback()


async def analyze_tracks_batch(
    db: AsyncSession,
    track_items: list[dict],
    task_id: str,
    results_store: dict,
) -> None:
    """Orchestrazione analisi batch con progress tracking.

    Args:
        track_items: lista di {id, preview_url, name, artist}
        task_id: UUID del task per polling
        results_store: dict condiviso per aggiornare progresso
    """
    from app.services.rapidapi_bridge import fetch_features_rapidapi

    total = len(track_items)
    completed = 0
    results: dict[str, dict] = {}

    # 1. Check cache DB
    track_ids = [t["id"] for t in track_items]
    cached = await get_or_fetch_features(db, track_ids)

    for tid, feat in cached.items():
        results[tid] = {**feat, "source": "cache"}
        completed += 1

    results_store[task_id]["completed"] = completed
    results_store[task_id]["results"] = dict(results)

    # 2. Analizza tracce non in cache
    uncached = [t for t in track_items if t["id"] not in cached]

    for track in uncached:
        tid = track["id"]
        preview_url = track.get("preview_url")
        features = None

        try:
            # Prova librosa se c'e' un preview URL
            if preview_url:
                features = await extract_features_from_url(preview_url)
                if features:
                    features["source"] = "librosa"

            # Fallback a RapidAPI se non c'e' preview o librosa ha fallito
            if not features:
                rapid_features = await fetch_features_rapidapi(
                    tid, track.get("name", ""), track.get("artist", "")
                )
                if rapid_features:
                    features = {**rapid_features, "source": "rapidapi"}

            if features:
                results[tid] = features
                # Salva in DB senza il campo "source" (non-blocking)
                db_features = {k: v for k, v in features.items() if k != "source"}
                try:
                    await _save_features_to_db(db, tid, db_features)
                except Exception as db_exc:
                    logger.warning("DB save fallito per %s: %s", tid, db_exc)
            else:
                results[tid] = {"source": "unavailable"}

        except SpotifyAuthError:
            # Non possiamo fare niente, segna come non disponibile
            results[tid] = {"source": "auth_error"}
            logger.warning("Auth error durante analisi di %s", tid)
        except Exception as exc:
            results[tid] = {"source": "error"}
            logger.warning("Errore analisi traccia %s: %s", tid, exc)

        completed += 1
        results_store[task_id]["completed"] = completed
        results_store[task_id]["results"] = dict(results)

    # Segna come completato
    results_store[task_id]["status"] = "completed"
    results_store[task_id]["completed"] = total
    results_store[task_id]["results"] = results
    logger.info(
        "Analisi batch %s completata: %d/%d tracce analizzate",
        task_id,
        sum(
            1
            for r in results.values()
            if r.get("source") not in ("unavailable", "error", "auth_error")
        ),
        total,
    )
