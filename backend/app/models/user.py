from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from app.database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    spotify_id = Column(String(255), unique=True, nullable=False, index=True)
    display_name = Column(String(255))
    email = Column(String(255))
    avatar_url = Column(Text)
    country = Column(String(10))
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    token = relationship("SpotifyToken", back_populates="user", uselist=False, cascade="all, delete-orphan")


class SpotifyToken(Base):
    __tablename__ = "spotify_tokens"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False)
    access_token_encrypted = Column(Text, nullable=False)
    refresh_token_encrypted = Column(Text, nullable=False)
    expires_at = Column(DateTime, nullable=False)
    scope = Column(Text)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user = relationship("User", back_populates="token")
