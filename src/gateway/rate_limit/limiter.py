"""Fixed-window request counters in Redis, one key per (scope, one-minute
bucket). Simple and fast, at the cost of the well-known fixed-window
tradeoff: a client can burst up to ~2x the limit across a window boundary
(e.g. 50 requests in the last second of one minute, another 50 in the
first second of the next, both windows individually compliant). A sliding
window or token bucket avoids that at the cost of more Redis state per
scope - not built here; this is the "Redis-backed counters" version the
plan called for, not the more precise one.
"""

import time
import uuid

from gateway.redis_client import redis_client

WINDOW_SECONDS = 60


def _bucket_key(scope_label: str, scope_id: uuid.UUID) -> str:
    window = int(time.time() // WINDOW_SECONDS)
    return f"ratelimit:{scope_label}:{scope_id}:{window}"


async def check_and_increment(
    scope_label: str, scope_id: uuid.UUID, limit_rpm: int
) -> tuple[bool, int]:
    """Atomically increments this scope's counter for the current window
    and checks it against limit_rpm. Returns (allowed, current_count).

    The increment happens regardless of the outcome - a rejected request
    still occupies a slot in the window. That's deliberate: it's what stops
    a client's retry storm from just retrying its way past the limit.
    """
    key = _bucket_key(scope_label, scope_id)
    count = await redis_client.incr(key)
    if count == 1:
        # Only the request that creates the key sets its expiry - repeating
        # this on every increment would keep extending the window instead
        # of letting it end on schedule.
        await redis_client.expire(key, WINDOW_SECONDS * 2)
    return count <= limit_rpm, count


async def get_current_count(scope_label: str, scope_id: uuid.UUID) -> int:
    """Read-only, for the status/debug endpoint - does not increment."""
    value = await redis_client.get(_bucket_key(scope_label, scope_id))
    return int(value) if value is not None else 0
