"""Cache persistente metadati playlist (track_count, nome, immagine)."""

from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
)

from app.database import Base


class PlaylistMetadata(Base):
    """Cache DB per metadati playlist — evita burst API per track_count=0 in dev mode."""

    __tablename__ = "playlist_metadata"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    playlist_id = Column(String(64), nullable=False)
    track_count = Column(Integer, default=0)
    name = Column(String(500), default="")
    image_url = Column(String, nullable=True)
    is_owner = Column(Boolean, default=True)
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    __table_args__ = (
        UniqueConstraint("user_id", "playlist_id", name="uq_playlist_metadata_user_pid"),
    )
