from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, Float, Integer, String, Text

from app.database import Base


class ListeningSnapshot(Base):
    """Snapshot periodico delle medie audio features dell'utente."""

    __tablename__ = "listening_snapshots"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, nullable=False, index=True)
    period = Column(String(20), nullable=False)  # 'short_term', 'medium_term', 'long_term'
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
