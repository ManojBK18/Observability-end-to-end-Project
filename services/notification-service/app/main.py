"""
main.py — Notification Service
-------------------------------------------------------------------------------
This is a "leaf" service in the trace tree: it doesn't call anything else,
it just does its job and returns. In Jaeger's trace view, this shows up as
a span with no children — useful for understanding what a "terminal" span
looks like versus order-service's "parent" span with multiple children.

We deliberately simulate a SLOW and sometimes FAILING dependency (an email
provider) so you have something realistic to find when you go looking at
traces and metrics later — a constant 10ms "perfect" service teaches you
nothing about debugging.
-------------------------------------------------------------------------------
"""

import asyncio
import random
import time

from fastapi import FastAPI
from pydantic import BaseModel

from app.tracing import setup_observability
from app.logger import get_logger
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry import trace

SERVICE_NAME = "notification-service"
tracer, meter = setup_observability(SERVICE_NAME)
logger = get_logger(SERVICE_NAME)

app = FastAPI(title="Notification Service")
FastAPIInstrumentor.instrument_app(app)

notifications_sent_counter = meter.create_counter(
    "notifications.sent_total", description="Total notifications successfully sent"
)
notifications_failed_counter = meter.create_counter(
    "notifications.failed_total", description="Total notifications that failed to send"
)
send_duration_histogram = meter.create_histogram(
    "notifications.send_duration_ms", description="Time taken to send a notification", unit="ms"
)


class NotificationRequest(BaseModel):
    order_id: str
    customer_email: str
    message: str


async def simulate_email_provider_call():
    """
    Fake call to an external email provider (e.g. SES, SendGrid).
    Randomised latency + occasional failure — this is what gives you
    something real to observe in metrics/traces/logs once deployed.
    """
    # Manual child span: this is how you instrument code that ISN'T
    # automatically covered by a library instrumentation package.
    with tracer.start_as_current_span("email_provider.send") as span:
        latency = random.uniform(0.05, 0.6)  # 50ms - 600ms, simulates real-world variance
        span.set_attribute("email_provider.simulated_latency_ms", round(latency * 1000, 2))
        await asyncio.sleep(latency)

        if random.random() < 0.1:  # 10% simulated failure rate
            span.set_attribute("email_provider.success", False)
            raise ConnectionError("Simulated email provider timeout")

        span.set_attribute("email_provider.success", True)


@app.get("/health")
async def health():
    return {"status": "ok", "service": SERVICE_NAME}


@app.post("/notify")
async def send_notification(notification: NotificationRequest):
    start_time = time.time()
    logger.info(
        "Notification request received",
        extra={"order_id": notification.order_id, "customer_email": notification.customer_email},
    )

    try:
        await simulate_email_provider_call()
    except ConnectionError as exc:
        notifications_failed_counter.add(1, {"reason": "provider_error"})
        duration_ms = round((time.time() - start_time) * 1000, 2)
        send_duration_histogram.record(duration_ms, {"outcome": "failed"})
        logger.error(
            "Failed to send notification",
            extra={"order_id": notification.order_id, "error": str(exc), "duration_ms": duration_ms},
        )
        # Mark the current span as an error so it's visually flagged in Jaeger.
        trace.get_current_span().record_exception(exc)
        return {"status": "failed", "order_id": notification.order_id}

    duration_ms = round((time.time() - start_time) * 1000, 2)
    notifications_sent_counter.add(1)
    send_duration_histogram.record(duration_ms, {"outcome": "success"})
    logger.info(
        "Notification sent successfully",
        extra={"order_id": notification.order_id, "duration_ms": duration_ms},
    )

    return {"status": "sent", "order_id": notification.order_id}

