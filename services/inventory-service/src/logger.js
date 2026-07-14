// logger.js
// -----------------------------------------------------------------------------
// Why this file exists: metrics tell you THAT something is slow/broken.
// Traces tell you WHERE in the request path it happened.
// Logs tell you WHY (the actual error message, stack trace, business context).
//
// The thing that ties all three together is the trace_id. If every log line
// is tagged with the trace_id of the request it happened during, you can
// jump from a slow trace in Jaeger straight to the exact log lines for that
// request in Grafana/Loki. That correlation is the whole point of this file.
// -----------------------------------------------------------------------------

const winston = require('winston');
const { trace, context } = require('@opentelemetry/api');

const logger = winston.createLogger({
  level: process.env.LOG_LEVEL || 'info',
  format: winston.format.combine(
    winston.format.timestamp(),
    winston.format.printf(({ timestamp, level, message, ...meta }) => {
      // Pull the active span out of OTel's context, if one exists.
      // This works because auto-instrumentation already created a span
      // for the current HTTP request by the time this log line runs.
      const span = trace.getSpan(context.active());
      const spanContext = span?.spanContext();

      const logObject = {
        timestamp,
        level,
        message,
        service: 'inventory-service',
        trace_id: spanContext?.traceId || null,
        span_id: spanContext?.spanId || null,
        ...meta,
      };
      // JSON logs (not pretty text) because Loki/CloudWatch/ELK all expect
      // structured logs they can parse and index by field.
      return JSON.stringify(logObject);
    })
  ),
  transports: [new winston.transports.Console()],
});

module.exports = logger;

