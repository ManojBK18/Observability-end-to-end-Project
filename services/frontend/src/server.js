// server.js — Frontend (BFF: Backend-For-Frontend)
// -----------------------------------------------------------------------------
// This is the entry point of the whole system — the span this creates is the
// ROOT SPAN of every trace. Everything downstream (order-service ->
// inventory-service / notification-service) becomes a child of this span.
//
// In a real app this would serve HTML/JS to a browser. Here it's just an API
// gateway — the point is to see a trace with 4 services in it, not to build
// a UI.
// -----------------------------------------------------------------------------

const express = require('express');
const axios = require('axios');
const logger = require('./logger');

const app = express();
app.use(express.json());

const PORT = process.env.PORT || 3000;
const ORDER_SERVICE_URL = process.env.ORDER_SERVICE_URL || 'http://order-service:8000';

app.get('/health', (req, res) => {
  res.json({ status: 'ok', service: 'frontend' });
});

// Simple HTML form so a human can place a test order from a browser,
// not just curl. Deliberately minimal — no CSS framework, no build step.
app.get('/', (req, res) => {
  res.send(`
    <html>
      <body style="font-family: sans-serif; max-width: 500px; margin: 50px auto;">
        <h2>Place an Order</h2>
        <form id="orderForm">
          <label>SKU: <input name="sku" value="sku-001" /></label><br/><br/>
          <label>Quantity: <input name="quantity" type="number" value="2" /></label><br/><br/>
          <label>Unit Price: <input name="unit_price" type="number" value="29.99" /></label><br/><br/>
          <label>Email: <input name="customer_email" value="test@example.com" /></label><br/><br/>
          <button type="submit">Place Order</button>
        </form>
        <pre id="result"></pre>
        <script>
          document.getElementById('orderForm').onsubmit = async (e) => {
            e.preventDefault();
            const data = Object.fromEntries(new FormData(e.target));
            data.quantity = parseInt(data.quantity);
            data.unit_price = parseFloat(data.unit_price);
            const res = await fetch('/api/orders', {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify(data),
            });
            document.getElementById('result').textContent = JSON.stringify(await res.json(), null, 2);
          };
        </script>
      </body>
    </html>
  `);
});

app.post('/api/orders', async (req, res) => {
  logger.info('Incoming order request from client', { body: req.body });

  try {
    // This axios call is auto-instrumented: a child span is created, and
    // the W3C "traceparent" header is automatically attached so order-service
    // continues this same trace instead of starting a new one.
    const response = await axios.post(`${ORDER_SERVICE_URL}/orders`, req.body, {
      timeout: 8000,
    });
    logger.info('Order placed successfully', { order_id: response.data.order_id });
    res.json(response.data);
  } catch (err) {
    const status = err.response?.status || 502;
    const detail = err.response?.data?.detail || 'Order service unavailable';
    logger.error('Order placement failed', { status, detail, error: err.message });
    res.status(status).json({ error: detail });
  }
});

app.get('/api/orders/:orderId', async (req, res) => {
  try {
    const response = await axios.get(`${ORDER_SERVICE_URL}/orders/${req.params.orderId}`);
    res.json(response.data);
  } catch (err) {
    const status = err.response?.status || 502;
    res.status(status).json({ error: 'Order not found' });
  }
});

app.listen(PORT, () => {
  logger.info(`Frontend listening on port ${PORT}`);
});

