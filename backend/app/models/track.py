from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, Float, Integer, String, Text

from app.database import Base


class AudioFeatures(Base):
    __tablename__ = "audio_features"

    id = Column(Integer, primary_key=True, autoincrement=True)
    track_spotify_id = Column(String(255), unique=True, nullable=False, index=True)
    danceability = Column(Float)
    energy = Column(Float)
    valence = Column(Float)
    acousticness = Column(Float)
    instrumentalness = Column(Float)
    liveness = Column(Float)
    speechiness = Column(Float)
    tempo = Column(Float)
    loudness = Column(Float)
    key = Column(Integer)
    mode = Column(Integer)
    time_signature = Column(Integer)
    cached_at = Column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )


class ArtistGenre(Base):
    """Cache persistente generi artista (TTL 7 giorni)."""

    __tablename__ = "artist_genres"

    id = Column(Integer, primary_key=True, autoincrement=True)
    artist_spotify_id = Column(String(64), unique=True, nullable=False, index=True)
    artist_name = Column(String(500), nullable=True)
    genres = Column(Text, nullable=False, default="[]")  # JSON array of strings
    cached_at = Column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )


class TrackPopularity(Base):
    """Cache per popularity dei brani (enrichment centralizzato)."""

    __tablename__ = "track_popularity"

    id = Column(Integer, primary_key=True, autoincrement=True)
    track_spotify_id = Column(String(255), unique=True, nullable=False, index=True)
    popularity = Column(Integer, nullable=False, default=0)
    cached_at = Column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
