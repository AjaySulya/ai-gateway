"""Tracer/meter setup plus the shared instruments the rest of the gateway
records against. Import `tracer` for spans and the `*_counter`/`*_latency`
instruments for metrics - don't create new meters/tracers elsewhere, or
their spans/metrics won't share this module's exporter configuration.

Exporting: unset OTEL_EXPORTER_OTLP_ENDPOINT (the default) prints spans and
metrics to stdout via the SDK's built-in console exporters - no collector
needed, which is what makes this runnable/inspectable without any extra
infrastructure. Set it to a collector URL (Grafana Tempo, an OTel Collector,
Honeycomb, etc.) to export via OTLP/HTTP instead; nothing else changes.
"""

import logging

from opentelemetry import metrics, trace
from opentelemetry.exporter.otlp.proto.http.metric_exporter import OTLPMetricExporter
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import ConsoleMetricExporter, PeriodicExportingMetricReader
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter

from gateway.config import settings

_SERVICE_NAME = "ai-gateway"


class _TraceContextFilter(logging.Filter):
    """Injects the current span's trace/span id into every log record, so
    a log line and the span it happened during can be correlated by
    trace_id without a separate logging backend."""

    def filter(self, record: logging.LogRecord) -> bool:
        ctx = trace.get_current_span().get_span_context()
        record.trace_id = format(ctx.trace_id, "032x") if ctx.trace_id else "-"
        record.span_id = format(ctx.span_id, "016x") if ctx.span_id else "-"
        return True


def _configure_logging() -> None:
    handler = logging.StreamHandler()
    handler.addFilter(_TraceContextFilter())
    handler.setFormatter(
        logging.Formatter(
            "%(asctime)s %(levelname)s [trace_id=%(trace_id)s span_id=%(span_id)s] "
            "%(name)s: %(message)s"
        )
    )
    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(logging.INFO)


def configure_observability() -> None:
    """Called once, from main.py's lifespan startup."""
    resource = Resource.create({"service.name": _SERVICE_NAME})

    span_exporter = (
        OTLPSpanExporter(endpoint=settings.otel_exporter_otlp_endpoint)
        if settings.otel_exporter_otlp_endpoint
        else ConsoleSpanExporter()
    )
    tracer_provider = TracerProvider(resource=resource)
    tracer_provider.add_span_processor(BatchSpanProcessor(span_exporter))
    trace.set_tracer_provider(tracer_provider)

    metric_exporter = (
        OTLPMetricExporter(endpoint=settings.otel_exporter_otlp_endpoint)
        if settings.otel_exporter_otlp_endpoint
        else ConsoleMetricExporter()
    )
    reader = PeriodicExportingMetricReader(metric_exporter, export_interval_millis=15_000)
    meter_provider = MeterProvider(resource=resource, metric_readers=[reader])
    metrics.set_meter_provider(meter_provider)

    _configure_logging()


def shutdown_observability() -> None:
    """Called from main.py's lifespan shutdown - flushes anything the
    BatchSpanProcessor/PeriodicExportingMetricReader is still holding."""
    trace.get_tracer_provider().shutdown()
    metrics.get_meter_provider().shutdown()


# Shared instruments - imported by gateway.api.chat (spans) and
# gateway.usage.tracker (metrics), rather than each module making its own.
#
# Safe to create these at import time, before configure_observability() has
# run: the OTel API returns proxy tracer/meter objects until a real
# provider is registered via set_tracer_provider()/set_meter_provider(),
# and those proxies delegate to the real thing retroactively once it is -
# this is the API's documented mechanism for exactly this import-order
# problem, not a workaround.
tracer = trace.get_tracer(_SERVICE_NAME)
meter = metrics.get_meter(_SERVICE_NAME)

request_counter = meter.create_counter(
    "gateway.requests", description="Data-plane chat completion requests", unit="1"
)
request_latency = meter.create_histogram(
    "gateway.request.duration", description="End-to-end request latency", unit="ms"
)
token_counter = meter.create_counter("gateway.tokens", description="Tokens processed", unit="1")
cost_counter = meter.create_counter(
    "gateway.cost", description="Estimated provider cost", unit="usd"
)
