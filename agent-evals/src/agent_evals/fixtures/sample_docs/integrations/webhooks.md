# Webhook Integration

Sending and receiving webhooks in DataForge.

## Sending Webhooks

```python
from framework.webhooks import WebhookSender

sender = WebhookSender()
await sender.send(
    url="https://api.partner.com/webhook",
    event="order.completed",
    payload={"order_id": 123, "total": 99.99},
)
```

## Receiving Webhooks

```python
from framework.webhooks import verify_signature

@app.post("/webhooks/stripe")
async def handle_stripe(request: Request):
    payload = await request.body()
    verify_signature(payload, request.headers["stripe-signature"])
    event = json.loads(payload)
    await process_stripe_event(event)
```

## Retry Policy

Failed webhook deliveries retry with exponential backoff:
- Attempt 1: immediate
- Attempt 2: 1 minute
- Attempt 3: 5 minutes
- Attempt 4: 30 minutes
- Attempt 5: 2 hours

See [Error Handling](../api/errors.md) for webhook error responses.
