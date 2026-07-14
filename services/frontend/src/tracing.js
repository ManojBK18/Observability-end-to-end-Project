// tracing.js
// -----------------------------------------------------------------------------
// This file MUST be loaded before any other code (see package.json: --require).
// That's how auto-instrumentation works: it patches libraries (http, express,
// pg, etc.) at require-time, so it has to run first.
// -----------------------------------------------------------------------------

const { NodeSDK } = require('@opentelemetry/sdk-node');
const { getNodeAutoInstrumentations } = require('@opentelemetry/auto-instrumentations-node');
const { OTLPTraceExporter } = require('@opentelemetry/exporter-trace-otlp-grpc');
const { OTLPMetricExporter } = require('@opentelemetry/exporter-metrics-otlp-grpc');
const { PeriodicExportingMetricReader } = require('@opentelemetry/sdk-metrics');
const { Resource } = require('@opentelemetry/resources');
const { SemanticResourceAttributes } = require('@opentelemetry/semantic-conventions');

// The OTel Collector's address. In Kubernetes this is a Service DNS name —
// every pod in the cluster can resolve "otel-collector" because it's a
// ClusterIP Service. Locally (docker-compose) it's just the container name.
const COLLECTOR_ENDPOINT = process.env.OTEL_COLLECTOR_ENDPOINT || 'otel-collector:4317';

// "Resource" = metadata attached to EVERY span/metric this service emits.
// This is what lets Grafana/Jaeger show "this trace came from frontend".
const resource = new Resource({
  [SemanticResourceAttributes.SERVICE_NAME]: 'frontend',
  [SemanticResourceAttributes.SERVICE_VERSION]: '1.0.0',
  [SemanticResourceAttributes.DEPLOYMENT_ENVIRONMENT]: process.env.ENVIRONMENT || 'development',
});

const traceExporter = new OTLPTraceExporter({
  url: `http://${COLLECTOR_ENDPOINT}`,
});

const metricExporter = new OTLPMetricExporter({
  url: `http://${COLLECTOR_ENDPOINT}`,
});

const sdk = new NodeSDK({
  resource,
  traceExporter,
  metricReader: new PeriodicExportingMetricReader({
    exporter: metricExporter,
    exportIntervalMillis: 10000, // push metrics every 10s
  }),
  // Auto-instrumentations patch express, http, and other common libraries
  // so you get spans for "incoming HTTP request", "outgoing HTTP call", etc.
  // WITHOUT writing any manual span code for the basics.
  instrumentations: [
    getNodeAutoInstrumentations({
      // fs instrumentation is extremely noisy (fires on every file read) —
      // disable it so traces stay readable.
      '@opentelemetry/instrumentation-fs': { enabled: false },
    }),
  ],
});

sdk.start();
console.log('[tracing] OpenTelemetry SDK started, exporting to', COLLECTOR_ENDPOINT);

// Graceful shutdown — flush any buffered spans/metrics before the process exits.
process.on('SIGTERM', () => {
  sdk.shutdown()
    .then(() => console.log('[tracing] SDK shut down cleanly'))
    .catch((err) => console.error('[tracing] Error shutting down SDK', err))
    .finally(() => process.exit(0));
});

module.exports = sdk;

