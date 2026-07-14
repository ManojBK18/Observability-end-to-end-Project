"""
logger.py
-------------------------------------------------------------------------------
Mirrors the Node.js logger.js: every log line gets the current trace_id and
span_id injected automatically, so logs and traces correlate in Grafana.
-------------------------------------------------------------------------------
"""

import logging
import sys
from pythonjsonlogger import jsonlogger
from opentelemetry import trace


class TraceContextFilter(logging.Filter):
    """Injects trace_id/span_id from the currently active OTel span, if any."""

    def filter(self, record):
        span = trace.get_current_span()
        span_context = span.get_span_context()
        if span_context and span_context.is_valid:
            record.trace_id = format(span_context.trace_id, "032x")
            record.span_id = format(span_context.span_id, "016x")
        else:
            record.trace_id = None
            record.span_id = None
        return True


def get_logger(service_name: str) -> logging.Logger:
    logger = logging.getLogger(service_name)
    logger.setLevel(logging.INFO)

    handler = logging.StreamHandler(sys.stdout)
    formatter = jsonlogger.JsonFormatter(
        "%(timestamp)s %(level)s %(name)s %(message)s %(trace_id)s %(span_id)s",
        rename_fields={"name": "service", "levelname": "level"},
        timestamp=True,
    )
    handler.setFormatter(formatter)
    handler.addFilter(TraceContextFilter())

    logger.handlers = [handler]
    logger.propagate = False
    return logger

