from datetime import datetime

from sqlalchemy import Column, DateTime, Float, Integer, String, Text

from app.database import Base


class Track(Base):
    __tablename__ = "tracks"

    id = Column(Integer, primary_key=True, autoincrement=True)
    spotify_id = Column(String(255), unique=True, nullable=False, index=True)
    name = Column(String(500), nullable=False)
    artist_name = Column(String(500))
    artist_id = Column(String(255))
    album_name = Column(String(500))
    album_image_url = Column(Text)
    duration_ms = Column(Integer)
    popularity = Column(Integer)
    preview_url = Column(Text)
    cached_at = Column(DateTime, default=datetime.utcnow)


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
    cached_at = Column(DateTime, default=datetime.utcnow)
