# Status Codes Reference

HTTP status codes used by the DataForge API.

## Success Codes

| Code | Name | Usage |
|------|------|-------|
| 200 | OK | Successful GET, PATCH, DELETE |
| 201 | Created | Successful POST creating a resource |
| 204 | No Content | Successful DELETE with no body |

## Client Error Codes

| Code | Name | Usage |
|------|------|-------|
| 400 | Bad Request | Malformed request syntax |
| 401 | Unauthorized | Missing or invalid auth token |
| 403 | Forbidden | Valid token but insufficient permissions |
| 404 | Not Found | Resource does not exist |
| 409 | Conflict | Duplicate or state conflict |
| 413 | Payload Too Large | File upload exceeds limit |
| 422 | Unprocessable Entity | Validation failure |
| 429 | Too Many Requests | Rate limit exceeded |

## Server Error Codes

| Code | Name | Usage |
|------|------|-------|
| 500 | Internal Server Error | Unhandled exception |
| 502 | Bad Gateway | Upstream service failure |
| 503 | Service Unavailable | Maintenance or overload |

See [Error Handling](../api/errors.md) for response format.
