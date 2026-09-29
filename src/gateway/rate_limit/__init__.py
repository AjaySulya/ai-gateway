"""Phase 6 - rate limiting.

- limiter.py       fixed-window request counters in Redis (one key per
                    scope per one-minute bucket)
- enforcement.py    per-level walk (org -> team -> project -> agent),
                    checking each level's own rate_limit_rpm against that
                    level's own count - same shape as usage/budgets.py's
                    per-level check, and for the same reason

Also moved Rate Limiting ahead of the Policy Engine in gateway.api.chat, to
match the pipeline order in the original architecture diagram - it hadn't
been built yet when Phases 3 and 5 landed, so the request handler's actual
order was Policy -> Budget until this phase corrected it.
"""
