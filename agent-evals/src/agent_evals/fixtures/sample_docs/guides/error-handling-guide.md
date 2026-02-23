# Error Handling Guide

Best practices for handling errors across your DataForge application.

## Layered Error Strategy

1. **Route layer**: Catch known errors, return appropriate HTTP status
2. **Service layer**: Raise domain-specific exceptions
3. **Middleware**: Catch unhandled exceptions, log and return 500

## Custom Exceptions

```python
from framework.errors import DomainError

class InsufficientFundsError(DomainError):
    code = "INSUFFICIENT_FUNDS"
    status_code = 422
```

## Error Logging

Errors are automatically logged with context:

```python
logger.error("Payment failed", extra={
    "user_id": user.id,
    "amount": amount,
    "error_code": exc.code,
})
```

See [Error Handling](../api/errors.md) for response format and [Logging](../api/logging.md) for log configuration.
