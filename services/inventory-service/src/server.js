// server.js
const express = require('express');
const { metrics } = require('@opentelemetry/api');
const logger = require('./logger');

const app = express();
app.use(express.json());

const PORT = process.env.PORT || 4000;

// ── In-memory "database" ────────────────────────────────────────────────────
// Deliberately simple — a real DB would add noise to what we're trying to
// learn here. Swap this for Postgres later once observability concepts click.
const stock = {
  'sku-001': { name: 'Wireless Mouse', quantity: 50 },
  'sku-002': { name: 'Mechanical Keyboard', quantity: 30 },
  'sku-003': { name: 'USB-C Hub', quantity: 0 }, // intentionally out of stock
};

// ── Custom business metrics ─────────────────────────────────────────────────
// Auto-instrumentation gives you free metrics like http_server_duration.
// But "how many times did we fail to reserve stock because of insufficient
// quantity" is a BUSINESS metric — nobody gives you that for free. You have
// to define it yourself. This is the pattern for that.
const meter = metrics.getMeter('inventory-service');

const stockCheckCounter = meter.createCounter('inventory.stock_checks_total', {
  description: 'Total number of stock check requests',
});

const insufficientStockCounter = meter.createCounter('inventory.insufficient_stock_total', {
  description: 'Number of times a reservation failed due to insufficient stock',
});

const reservationDurationHistogram = meter.createHistogram('inventory.reservation_duration_ms', {
  description: 'Time taken to process a stock reservation',
  unit: 'ms',
});

// ── Routes ───────────────────────────────────────────────────────────────────

app.get('/health', (req, res) => {
  res.json({ status: 'ok', service: 'inventory-service' });
});

app.get('/inventory/:sku', (req, res) => {
  const { sku } = req.params;
  stockCheckCounter.add(1, { sku });

  const item = stock[sku];
  logger.info('Stock check requested', { sku, found: !!item });

  if (!item) {
    return res.status(404).json({ error: 'SKU not found' });
  }
  res.json({ sku, ...item });
});

// Order-service calls this to reserve stock before confirming an order.
app.post('/inventory/:sku/reserve', (req, res) => {
  const start = Date.now();
  const { sku } = req.params;
  const { quantity } = req.body;

  const item = stock[sku];

  if (!item) {
    logger.warn('Reservation failed: SKU not found', { sku });
    return res.status(404).json({ error: 'SKU not found' });
  }

  if (item.quantity < quantity) {
    insufficientStockCounter.add(1, { sku });
    logger.warn('Reservation failed: insufficient stock', {
      sku,
      requested: quantity,
      available: item.quantity,
    });
    reservationDurationHistogram.record(Date.now() - start, { sku, outcome: 'failed' });
    return res.status(409).json({ error: 'Insufficient stock', available: item.quantity });
  }

  item.quantity -= quantity;
  logger.info('Stock reserved successfully', { sku, quantity, remaining: item.quantity });
  reservationDurationHistogram.record(Date.now() - start, { sku, outcome: 'success' });

  res.json({ sku, reserved: quantity, remaining: item.quantity });
});

app.listen(PORT, () => {
  logger.info(`Inventory service listening on port ${PORT}`);
});

