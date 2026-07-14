"""
tracing.py
-------------------------------------------------------------------------------
Same job as the Node.js tracing.js, but using the Python OTel SDK. The two
SDKs look different syntactically but follow the exact same model:

  Resource (who am I)  ->  Exporter (where do I send data)  ->  Provider (the
  thing that actually creates spans/metrics) -> Instrumentation (auto-patches
  FastAPI/httpx so you get spans for free)

This is the piece that proves OpenTelemetry is vendor- AND language-neutral:
Node and Python services both end up sending identical OTLP data to the same
collector, and Jaeger/Grafana don't care which language produced which span.
-------------------------------------------------------------------------------
"""

import os

from opentelemetry import trace, metrics
from opentelemetry.sdk.resources import Resource, SERVICE_NAME, SERVICE_VERSION
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import OTLPMetricExporter

COLLECTOR_ENDPOINT = os.getenv("OTEL_COLLECTOR_ENDPOINT", "otel-collector:4317")
ENVIRONMENT = os.getenv("ENVIRONMENT", "development")


def setup_observability(service_name: str):
    """Call this once, at the very top of main.py, before creating the app."""

    resource = Resource.create({
        SERVICE_NAME: service_name,
        SERVICE_VERSION: "1.0.0",
        "deployment.environment": ENVIRONMENT,
    })

    # ── Tracing ──────────────────────────────────────────────────────────────
    trace_provider = TracerProvider(resource=resource)
    span_exporter = OTLPSpanExporter(endpoint=COLLECTOR_ENDPOINT, insecure=True)
    # BatchSpanProcessor buffers spans and sends them in batches instead of
    # one network call per span — this matters a lot under real load.
    trace_provider.add_span_processor(BatchSpanProcessor(span_exporter))
    trace.set_tracer_provider(trace_provider)

    # ── Metrics ──────────────────────────────────────────────────────────────
    metric_exporter = OTLPMetricExporter(endpoint=COLLECTOR_ENDPOINT, insecure=True)
    metric_reader = PeriodicExportingMetricReader(metric_exporter, export_interval_millis=10000)
    meter_provider = MeterProvider(resource=resource, metric_readers=[metric_reader])
    metrics.set_meter_provider(meter_provider)

    print(f"[tracing] OpenTelemetry initialised for '{service_name}', exporting to {COLLECTOR_ENDPOINT}")

    return trace.get_tracer(service_name), metrics.get_meter(service_name)

