from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, Float, Integer, String

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
    cached_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
