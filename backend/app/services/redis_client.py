"""Async Redis client singleton with connection pooling."""

import logging

import redis.asyncio as redis

from app.config import settings

logger = logging.getLogger(__name__)

_redis_client: redis.Redis | None = None


def get_redis() -> redis.Redis:
    """Return the singleton Redis client (lazy-initialized on first call).

    Uses a connection pool internally — safe for concurrent use.
    Raises ConnectionError if Redis is unreachable (caller decides how to handle).
    """
    global _redis_client
    if _redis_client is None:
        _redis_client = redis.from_url(
            settings.redis_url,
            decode_responses=True,
            max_connections=20,
        )
        logger.info("Redis client inizializzato: %s", settings.redis_url)
    return _redis_client


async def redis_ping() -> bool:
    """Return True if Redis responds to PING, False otherwise."""
    try:
        client = get_redis()
        return await client.ping()
    except Exception as exc:
        logger.warning("Redis ping fallito: %s", exc)
        return False


async def close_redis() -> None:
    """Graceful shutdown — close the connection pool."""
    global _redis_client
    if _redis_client is not None:
        await _redis_client.aclose()
        _redis_client = None
        logger.info("Redis client chiuso")
