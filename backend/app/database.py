from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.config import settings

engine = create_async_engine(settings.database_url, echo=False)
async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


async def get_db():
    async with async_session() as session:
        yield session


async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        # Safe column additions for existing tables (idempotent)
        for stmt in [
            "ALTER TABLE recent_plays ADD COLUMN artist_spotify_id VARCHAR(64)",
        ]:
            try:
                await conn.execute(text(stmt))
            except Exception:
                pass  # Column already exists
        # Composite index for Tier 1 aggregations
        try:
            await conn.execute(
                text(
                    "CREATE INDEX IF NOT EXISTS ix_recent_plays_user_played "
                    "ON recent_plays(user_id, played_at)"
                )
            )
        except Exception:
            pass
