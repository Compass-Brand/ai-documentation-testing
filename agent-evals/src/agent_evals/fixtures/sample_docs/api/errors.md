# Error Handling

All API errors follow a consistent JSON envelope format.

## Error Response Format

```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Field 'email' is required.",
    "details": [
      {"field": "email", "constraint": "required"}
    ]
  }
}
```

## Status Code Reference

- `400 Bad Request` -- Validation failures, malformed input
- `401 Unauthorized` -- Missing or expired authentication token
- `403 Forbidden` -- Insufficient permissions for the requested resource
- `404 Not Found` -- Resource does not exist
- `409 Conflict` -- Duplicate resource or state conflict
- `422 Unprocessable Entity` -- Semantically invalid request
- `429 Too Many Requests` -- Rate limit exceeded
- `500 Internal Server Error` -- Unhandled server exception

## Custom Exception Classes

```python
from framework.errors import APIError

raise APIError(
    status_code=409,
    code="DUPLICATE_EMAIL",
    message="A user with this email already exists.",
)
```

Unhandled exceptions are caught by the error middleware and returned as 500 errors. See [Middleware](middleware.md) for the error propagation chain and [Authentication](auth.md) for auth-specific errors.
