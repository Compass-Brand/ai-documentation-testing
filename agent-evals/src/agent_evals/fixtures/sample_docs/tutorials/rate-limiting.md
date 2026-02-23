# Tutorial: Rate Limiting

Protect your API with configurable rate limits.

## Basic Rate Limiting

```python
from framework.ratelimit import RateLimiter

limiter = RateLimiter(
    default_limit="100/minute",
    storage="redis://localhost:6379",
)
app.add_middleware(limiter.middleware)
```

## Per-Endpoint Limits

```python
@app.post("/api/auth/login")
@limiter.limit("5/minute")
async def login(data: LoginRequest):
    return await auth_service.login(data)

@app.get("/api/products")
@limiter.limit("200/minute")
async def list_products():
    return await product_service.list()
```

## Custom Keys

Rate limit by user ID instead of IP:

```python
@limiter.limit("50/minute", key_func=lambda req: req.state.user.id)
async def create_order(data: OrderRequest):
    ...
```

## Response Headers

Responses include rate limit headers:
- X-RateLimit-Limit: 100
- X-RateLimit-Remaining: 95
- X-RateLimit-Reset: 1640000000

See [Caching](../api/caching.md) for Redis configuration.
