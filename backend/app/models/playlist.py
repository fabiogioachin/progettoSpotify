from datetime import datetime

from sqlalchemy import Column, DateTime, Integer, String, Text

from app.database import Base


class PlaylistCache(Base):
    __tablename__ = "playlist_cache"

    id = Column(Integer, primary_key=True, autoincrement=True)
    spotify_id = Column(String(255), unique=True, nullable=False, index=True)
    user_id = Column(Integer, nullable=False, index=True)
    name = Column(String(500))
    description = Column(Text)
    image_url = Column(Text)
    track_count = Column(Integer)
    owner_name = Column(String(255))
    snapshot_id = Column(String(255))
    cached_at = Column(DateTime, default=datetime.utcnow)
