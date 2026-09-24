"""Phase 6 - rate limiting.

Will hold: a Redis-backed limiter (token bucket or sliding window) enforced
as its own data-plane stage, using EffectivePolicy.rate_limit_rpm (see
gateway.policy.schemas) - resolved correctly today but not yet enforced.

Not implemented yet.
"""
