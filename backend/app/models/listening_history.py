from datetime import date, datetime, timezone

from sqlalchemy import (
    Column,
    Date,
    DateTime,
    Float,
    Integer,
    String,
    Text,
    UniqueConstraint,
)

from app.database import Base


class ListeningSnapshot(Base):
    """Snapshot periodico delle medie audio features dell'utente."""

    __tablename__ = "listening_snapshots"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, nullable=False, index=True)
    period = Column(
        String(20), nullable=False
    )  # 'short_term', 'medium_term', 'long_term'
    snapshot_date = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    avg_energy = Column(Float)
    avg_valence = Column(Float)
    avg_danceability = Column(Float)
    avg_acousticness = Column(Float)
    avg_instrumentalness = Column(Float)
    avg_speechiness = Column(Float)
    avg_liveness = Column(Float)
    avg_tempo = Column(Float)

    top_genre = Column(String(255))
    genre_distribution = Column(Text)  # JSON string
    track_count = Column(Integer)


class RecentPlay(Base):
    """Cronologia ascolti accumulata nel tempo (supera il limite di 50 di Spotify)."""

    __tablename__ = "recent_plays"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, nullable=False, index=True)
    track_spotify_id = Column(String(64), nullable=False)
    track_name = Column(String(500), nullable=False)
    artist_name = Column(String(500), nullable=False)
    artist_spotify_id = Column(String(64), nullable=True)
    duration_ms = Column(Integer, default=0)
    played_at = Column(DateTime, nullable=False, index=True)

    __table_args__ = (
        UniqueConstraint(
            "user_id", "track_spotify_id", "played_at", name="uq_user_track_played"
        ),
    )


class UserSnapshot(Base):
    """Snapshot giornaliero dei top artists/tracks dell'utente per confronti temporali."""

    __tablename__ = "user_snapshots"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, nullable=False, index=True)
    captured_at = Column(Date, nullable=False, default=lambda: date.today())
    top_artists_json = Column(Text, nullable=False, default="[]")
    top_tracks_json = Column(Text, nullable=False, default="[]")
    recent_plays_count = Column(Integer, default=0)

    __table_args__ = (
        UniqueConstraint("user_id", "captured_at", name="uq_user_snapshot_date"),
    )


class DailyListeningStats(Base):
    """Statistiche giornaliere aggregate per utente."""

    __tablename__ = "daily_listening_stats"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, nullable=False, index=True)
    date = Column(Date, nullable=False)
    total_plays = Column(Integer, default=0)
    unique_tracks = Column(Integer, default=0)
    unique_artists = Column(Integer, default=0)
    total_duration_ms = Column(Integer, default=0)
    top_genre = Column(String(255), nullable=True)
    avg_popularity = Column(Float, nullable=True)
    new_artists_count = Column(Integer, default=0)
    new_tracks_count = Column(Integer, default=0)
    peak_hour = Column(Integer, nullable=True)
    top_artist = Column(String(500), nullable=True)

    __table_args__ = (
        UniqueConstraint("user_id", "date", name="uq_daily_stats_user_date"),
    )


class UserProfileMetrics(Base):
    """Metriche profilo utente aggregate e persistenti."""

    __tablename__ = "user_profile_metrics"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, nullable=False, unique=True, index=True)
    obscurity_score = Column(Float, default=0.0)
    genre_diversity_index = Column(Float, default=0.0)
    artist_loyalty_score = Column(Float, default=0.0)
    listening_consistency = Column(Float, default=0.0)
    total_plays_lifetime = Column(Integer, default=0)
    total_artists_lifetime = Column(Integer, default=0)
    total_tracks_lifetime = Column(Integer, default=0)
    top_genres_json = Column(Text, default="[]")
    decade_distribution_json = Column(Text, default="{}")
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
