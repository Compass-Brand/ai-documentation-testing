# Authentication

The authentication module provides JWT-based identity verification for all API endpoints.

## Middleware Setup

Register the auth middleware in your application startup:

```python
from framework.auth import AuthMiddleware, JWTConfig

config = JWTConfig(
    secret_key=os.environ["JWT_SECRET"],
    algorithm="HS256",
    expiry_seconds=3600,
)
app.add_middleware(AuthMiddleware(config))
```

## Token Lifecycle

1. Client sends credentials to `/api/auth/login`
2. Server validates and returns an access token and refresh token
3. Access token expires after 1 hour; use `/api/auth/refresh` to renew
4. Refresh tokens are single-use and rotate on each refresh

## Protected Routes

Decorate endpoints with `@require_auth` to enforce authentication:

```python
@app.get("/api/users/me")
@require_auth
async def get_current_user(request: Request):
    return request.state.user
```

See also: [Users API](users.md) for user management, [Error Handling](errors.md) for 401/403 responses.
