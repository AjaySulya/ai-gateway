"""Phase 7 - observability.

otel.py holds tracer/meter setup (console exporters by default, OTLP if
OTEL_EXPORTER_OTLP_ENDPOINT is set), the shared request/latency/token/cost
instruments, and trace-correlated logging. gateway.api.chat wraps each
pipeline stage in a child span using otel.tracer; gateway.usage.tracker
records metrics from the same place it already writes UsageRecord rows,
rather than duplicating a call per pipeline exit path.

No SQLAlchemy auto-instrumentation (DB query spans) - a reasonable next
addition, not built here.
"""
