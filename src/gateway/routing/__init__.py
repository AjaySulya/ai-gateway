"""Phase 4 - Model Router.

- strategies.py       candidate resolution: every active (Model, Provider)
                       match for a requested model name, ordered by priority
- circuit_breaker.py   per-provider failure tracking in Redis; open/closed
                       derived from failure count + cooldown timestamp
- router.py            orchestrates the two above plus retry/backoff;
                       gateway.api.chat calls this instead of the old
                       single-candidate gateway.data_plane.model_resolution
                       (removed - this package replaces it)

TypeSafe Jev slots in later as a smarter candidate *orderer* in front of
strategies.get_candidates() - see README.md - now that this deterministic
path is in place.
"""

