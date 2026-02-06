# Logging

Structured logging support with configurable outputs and log levels.

## Setup

```python
from framework.logging import configure_logging

configure_logging(
    level=settings.log_level,
    format="json",  # or "text" for development
    output="stdout",
)
```

## Structured Log Fields

Every log entry includes standard fields:

```json
{
  "timestamp": "2025-01-15T10:30:00Z",
  "level": "INFO",
  "message": "Request processed",
  "request_id": "abc-123",
  "method": "GET",
  "path": "/api/users",
  "status": 200,
  "duration_ms": 45
}
```

## Adding Context

Use the context manager to attach fields to all logs within a scope:

```python
from framework.logging import log_context

async def handle_request(request):
    with log_context(user_id=request.user.id, tenant=request.tenant):
        logger.info("Processing request")
        # user_id and tenant appear in all logs within this block
```

## Log Levels

- `DEBUG` -- Detailed diagnostic information
- `INFO` -- General operational events
- `WARNING` -- Unexpected but recoverable situations
- `ERROR` -- Failures requiring attention
- `CRITICAL` -- System-level failures

Set the level via the `LOG_LEVEL` environment variable. See [Configuration](config.md) for all environment settings and [Middleware](middleware.md) for request-level logging.
