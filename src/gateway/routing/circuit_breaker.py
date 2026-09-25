"""Per-provider circuit breaker, backed by Redis so state is shared across
gateway processes/workers rather than living in-process.

Two keys per provider:
  circuit:{provider_id}:failures       consecutive failure count
  circuit:{provider_id}:opened_until   unix timestamp the circuit reopens at

There's no separate closed/open/half-open enum - all three are derived from
whether opened_until is set and in the future. A half-open trial is just
"opened_until has passed, so the next attempt is let through"; if it fails,
record_failure reopens the circuit with a fresh cooldown, and if it
succeeds, record_success clears both keys.
"""

import time
import uuid

from gateway.redis_client import redis_client

FAILURE_THRESHOLD = 5
COOLDOWN_SECONDS = 30


def _failures_key(provider_id: uuid.UUID) -> str:
    return f"circuit:{provider_id}:failures"


def _opened_until_key(provider_id: uuid.UUID) -> str:
    return f"circuit:{provider_id}:opened_until"


async def is_open(provider_id: uuid.UUID) -> bool:
    opened_until = await redis_client.get(_opened_until_key(provider_id))
    if opened_until is None:
        return False
    return time.time() < float(opened_until)


async def record_success(provider_id: uuid.UUID) -> None:
    await redis_client.delete(_failures_key(provider_id), _opened_until_key(provider_id))


async def record_failure(provider_id: uuid.UUID) -> None:
    failures = await redis_client.incr(_failures_key(provider_id))
    # Let the failure count expire on its own if the provider goes quiet,
    # rather than accumulating forever across unrelated incidents.
    await redis_client.expire(_failures_key(provider_id), COOLDOWN_SECONDS * 4)
    if failures >= FAILURE_THRESHOLD:
        await redis_client.set(
            _opened_until_key(provider_id),
            time.time() + COOLDOWN_SECONDS,
            ex=COOLDOWN_SECONDS,
        )


async def get_state(provider_id: uuid.UUID) -> dict:
    """For the debug endpoint - GET /providers/{id}/health."""
    failures_raw = await redis_client.get(_failures_key(provider_id))
    opened_until_raw = await redis_client.get(_opened_until_key(provider_id))
    return {
        "failures": int(failures_raw) if failures_raw is not None else 0,
        "circuit_open": await is_open(provider_id),
        "opened_until": float(opened_until_raw) if opened_until_raw is not None else None,
    }
