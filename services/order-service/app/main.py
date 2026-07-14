"""
main.py — Order Service
-------------------------------------------------------------------------------
This service is the "hub" of the trace. When a customer places an order:

  1. order-service receives the request          (span: POST /orders)
  2. order-service calls inventory-service        (span: HTTP GET/POST -> child span)
  3. order-service calls notification-service     (span: HTTP POST -> child span, fire-and-forget)

Because httpx is auto-instrumented, the trace context (trace_id) is
automatically injected into the outgoing HTTP headers (W3C traceparent header).
inventory-service and notification-service then pick that header up and
continue the SAME trace — this is what makes it "distributed" tracing instead
of three separate, disconnected traces.
-------------------------------------------------------------------------------
"""

import os
import time
import uuid

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import httpx

from app.tracing import setup_observability
from app.logger import get_logger
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor

SERVICE_NAME = "order-service"
tracer, meter = setup_observability(SERVICE_NAME)
logger = get_logger(SERVICE_NAME)

INVENTORY_URL = os.getenv("INVENTORY_SERVICE_URL", "http://inventory-service:4000")
NOTIFICATION_URL = os.getenv("NOTIFICATION_SERVICE_URL", "http://notification-service:5000")

app = FastAPI(title="Order Service")

# Auto-instrument FastAPI (creates a span for every incoming request)
# and httpx (creates a child span for every outgoing call, and propagates
# trace context in the request headers automatically).
FastAPIInstrumentor.instrument_app(app)
HTTPXClientInstrumentor().instrument()

# ── Custom business metrics ──────────────────────────────────────────────────
orders_created_counter = meter.create_counter(
    "orders.created_total", description="Total number of orders successfully created"
)
orders_failed_counter = meter.create_counter(
    "orders.failed_total", description="Total number of orders that failed (any reason)"
)
order_value_histogram = meter.create_histogram(
    "orders.value", description="Distribution of order values", unit="usd"
)

# In-memory order store — simple on purpose, same reasoning as inventory-service.
orders_db = {}


class OrderRequest(BaseModel):
    sku: str
    quantity: int
    unit_price: float
    customer_email: str


@app.get("/health")
async def health():
    return {"status": "ok", "service": SERVICE_NAME}


@app.post("/orders")
async def create_order(order: OrderRequest):
    order_id = str(uuid.uuid4())
    start_time = time.time()

    logger.info("Order received", extra={"order_id": order_id, "sku": order.sku, "quantity": order.quantity})

    # ── Step 1: Reserve stock from inventory-service ─────────────────────────
    # This HTTP call automatically becomes a CHILD SPAN of the current
    # "POST /orders" span, because httpx instrumentation propagates context.
    async with httpx.AsyncClient(timeout=5.0) as client:
        try:
            reserve_response = await client.post(
                f"{INVENTORY_URL}/inventory/{order.sku}/reserve",
                json={"quantity": order.quantity},
            )
        except httpx.RequestError as exc:
            orders_failed_counter.add(1, {"reason": "inventory_unreachable"})
            logger.error("Inventory service unreachable", extra={"order_id": order_id, "error": str(exc)})
            raise HTTPException(status_code=503, detail="Inventory service unavailable")

    if reserve_response.status_code == 409:
        orders_failed_counter.add(1, {"reason": "insufficient_stock"})
        logger.warning("Order failed: insufficient stock", extra={"order_id": order_id, "sku": order.sku})
        raise HTTPException(status_code=409, detail="Insufficient stock")

    if reserve_response.status_code == 404:
        orders_failed_counter.add(1, {"reason": "sku_not_found"})
        logger.warning("Order failed: SKU not found", extra={"order_id": order_id, "sku": order.sku})
        raise HTTPException(status_code=404, detail="SKU not found")

    # ── Step 2: Persist the order ─────────────────────────────────────────────
    total_value = round(order.quantity * order.unit_price, 2)
    orders_db[order_id] = {
        "order_id": order_id,
        "sku": order.sku,
        "quantity": order.quantity,
        "total_value": total_value,
        "customer_email": order.customer_email,
        "status": "confirmed",
    }

    # ── Step 3: Fire-and-forget notification ──────────────────────────────────
    # Deliberately NOT awaited-and-checked the same way — if notifications
    # are slow/down, that should not fail the order. This is also a nice
    # example for tracing: you'll see this child span complete independently.
    async with httpx.AsyncClient(timeout=3.0) as client:
        try:
            await client.post(
                f"{NOTIFICATION_URL}/notify",
                json={
                    "order_id": order_id,
                    "customer_email": order.customer_email,
                    "message": f"Your order {order_id} for {order.quantity}x {order.sku} is confirmed.",
                },
            )
        except httpx.RequestError as exc:
            # Logged but NOT raised — a failed notification shouldn't fail the order.
            logger.warning("Notification failed (non-fatal)", extra={"order_id": order_id, "error": str(exc)})

    orders_created_counter.add(1, {"sku": order.sku})
    order_value_histogram.record(total_value, {"sku": order.sku})

    duration_ms = round((time.time() - start_time) * 1000, 2)
    logger.info("Order confirmed", extra={"order_id": order_id, "duration_ms": duration_ms, "total_value": total_value})

    return orders_db[order_id]


@app.get("/orders/{order_id}")
async def get_order(order_id: str):
    order = orders_db.get(order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    return order

