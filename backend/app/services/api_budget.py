"""Priority-based API budget system for Spotify rate limiting.

Distributes the 25 calls/30s sliding window budget across priority tiers
so that interactive user requests are never starved by background jobs.

Reads from the same Redis sorted set used by SpotifyClient._throttle_check_and_register().
Member format: {uuid}:{priority}:{user_id}
"""

import logging
import math
import time
from enum import IntEnum

from app.services.redis_client import get_redis

logger = logging.getLogger(__name__)


class Priority(IntEnum):
    P0_INTERACTIVE = 0  # User page loads — 70% budget
    P1_BACKGROUND_SYNC = 1  # Login sync — 20% budget
    P2_BATCH = 2  # Hourly sync all users — 10% budget


TOTAL_BUDGET = 25  # calls per 30s (unchanged)
TIER_LIMITS = {
    Priority.P0_INTERACTIVE: 17,  # ~70%
    Priority.P1_BACKGROUND_SYNC: 5,  # ~20%
    Priority.P2_BATCH: 3,  # ~10%
}
MAX_USER_SHARE_MIN = 0.40  # Floor: with many users, no single user > 40%
MAX_USER_SHARE_MAX = 1.00  # Ceiling: solo user gets full tier budget

WINDOW_SIZE = 30  # seconds

# Redis key — same sorted set used by SpotifyClient throttle
_REDIS_CALLS_KEY = "ratelimit:spotify:calls"


async def check_budget(user_id: int, priority: Priority) -> bool:
    """Check if a call at this priority level is within budget.

    Returns True if allowed, False if budget exhausted for this tier.
    Fails-open on Redis errors (returns True).

    Reads the sorted set members which have format: {uuid}:{priority}:{user_id}
    """
    try:
        r = get_redis()
        now = time.time()
        window_start = now - WINDOW_SIZE

        # Get all members in the current window
        members = await r.zrangebyscore(_REDIS_CALLS_KEY, window_start, "+inf")

        # Count calls per tier, per user-in-tier, and distinct active users
        tier_count = 0
        user_count_in_tier = 0
        active_users: set[str] = set()
        user_id_str = str(user_id)
        priority_str = str(int(priority))

        for member in members:
            # member format: {uuid}:{priority}:{user_id}
            parts = member.split(":")
            if len(parts) >= 3:
                member_priority = parts[1]
                member_user_id = parts[2]
                active_users.add(member_user_id)
                if member_priority == priority_str:
                    tier_count += 1
                    if member_user_id == user_id_str:
                        user_count_in_tier += 1
            # Legacy members without priority encoding are ignored for tier counting

        tier_limit = TIER_LIMITS[priority]
        # Dynamic user share: 1 user → 100%, 2 → 50%, 3+ → floor at 40%
        n_users = max(1, len(active_users))
        user_share = max(MAX_USER_SHARE_MIN, min(MAX_USER_SHARE_MAX, 1.0 / n_users))
        user_limit = max(1, math.floor(tier_limit * user_share))

        if tier_count >= tier_limit:
            logger.info(
                "Budget esaurito per tier %s: %d/%d chiamate nella finestra",
                priority.name,
                tier_count,
                tier_limit,
            )
            return False

        if user_count_in_tier >= user_limit:
            logger.info(
                "Budget utente esaurito per user %s in tier %s: %d/%d chiamate",
                user_id,
                priority.name,
                user_count_in_tier,
                user_limit,
            )
            return False

        return True

    except Exception:
        logger.warning("Redis non disponibile per budget check — fail-open")
        return True  # fail-open


async def extend_cache_ttl(user_id: int, multiplier: int = 2):
    """Double cache TTLs for a user when budget is tight.

    Scans Redis keys matching cache:user:{user_id}:* and multiplies their TTL.
    Fails silently on Redis errors.
    """
    try:
        r = get_redis()
        pattern = f"cache:user:{user_id}:*"
        cursor = 0
        extended_count = 0

        while True:
            cursor, keys = await r.scan(cursor=cursor, match=pattern, count=100)
            for key in keys:
                ttl = await r.ttl(key)
                if ttl > 0:
                    new_ttl = ttl * multiplier
                    await r.expire(key, new_ttl)
                    extended_count += 1
            if cursor == 0:
                break

        if extended_count > 0:
            logger.info(
                "Cache TTL esteso x%d per user %s: %d chiavi aggiornate",
                multiplier,
                user_id,
                extended_count,
            )
    except Exception:
        logger.warning("Redis non disponibile per extend_cache_ttl — ignorato")
