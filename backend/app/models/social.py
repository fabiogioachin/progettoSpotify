"""Modelli per il layer social: amicizie, link di invito e codici di registrazione."""

from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, UniqueConstraint

from app.database import Base


class InviteCode(Base):
    """Codice di invito per la registrazione gated."""

    __tablename__ = "invite_codes"

    id = Column(Integer, primary_key=True, autoincrement=True)
    code = Column(String(32), unique=True, nullable=False, index=True)
    created_by = Column(
        Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    max_uses = Column(Integer, default=5)
    uses = Column(Integer, default=0)
    expires_at = Column(DateTime(timezone=True), nullable=True)  # null = never expires
    created_at = Column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )


class Friendship(Base):
    """Amicizia bidirezionale tra due utenti.

    Quando A diventa amico di B, vengono inserite DUE righe:
    (user_id=A, friend_id=B) e (user_id=B, friend_id=A).
    """

    __tablename__ = "friendships"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    friend_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    created_at = Column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    __table_args__ = (UniqueConstraint("user_id", "friend_id", name="uq_friendship"),)


class FriendInviteLink(Base):
    """Link di invito per aggiungere amici, con scadenza e limite di utilizzi."""

    __tablename__ = "friend_invite_links"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    code = Column(String(32), unique=True, nullable=False, index=True)
    created_at = Column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    expires_at = Column(
        DateTime(timezone=True), nullable=False
    )  # 7 giorni dalla creazione
    max_uses = Column(Integer, default=1)
    uses = Column(Integer, default=0)
