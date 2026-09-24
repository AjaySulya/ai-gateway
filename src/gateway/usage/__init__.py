"""Phase 5 - usage tracking and budget enforcement.

Will hold: a usage-record table (tokens, cost, latency, model, provider,
org/team/project, status) logged per request, and budget checks (soft/hard
caps) against aggregated usage. This is what makes
EffectivePolicy.budget_limit_usd (see gateway.policy.schemas) actually
enforceable - it's resolved correctly today but nothing checks against it
yet.

Not implemented yet.
"""
