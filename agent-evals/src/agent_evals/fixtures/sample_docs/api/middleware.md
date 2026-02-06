# Middleware

The middleware pipeline processes every request and response in a defined order.

## Built-in Middleware

The framework ships with several middleware components:

1. **RequestID** -- Assigns a unique `X-Request-ID` header to each request
2. **Logging** -- Logs request method, path, status code, and duration
3. **CORS** -- Handles cross-origin resource sharing headers
4. **Auth** -- Validates JWT tokens (see [Authentication](auth.md))
5. **RateLimit** -- Enforces per-client rate limiting

## Execution Order

Middleware executes in registration order for requests and reverse order for responses:

```
Request  -> RequestID -> Logging -> CORS -> Auth -> RateLimit -> Handler
Response <- RequestID <- Logging <- CORS <- Auth <- RateLimit <- Handler
```

## Custom Middleware

```python
from framework.middleware import BaseMiddleware

class TimingMiddleware(BaseMiddleware):
    async def process_request(self, request):
        request.state.start_time = time.monotonic()

    async def process_response(self, request, response):
        elapsed = time.monotonic() - request.state.start_time
        response.headers["X-Response-Time"] = f"{elapsed:.4f}s"
```

Register custom middleware in your configuration. See [Error Handling](errors.md) for middleware error propagation.
