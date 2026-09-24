"""Phase 7 - observability.

Will hold: OpenTelemetry tracer/meter setup and FastAPI instrumentation,
with a span per pipeline stage (auth, policy, routing, provider call) and
metrics sliced by org/team/project/model/provider. This is what makes
Phase 5's usage data trustworthy in production rather than just present.

Not implemented yet.
"""
