# API Versioning

Strategy for managing API version changes.

## URL-Based Versioning

```
https://api.example.com/v1/users
https://api.example.com/v2/users
```

## Configuring Versions

```python
from framework.versioning import APIVersion

v1 = APIVersion("v1")
v2 = APIVersion("v2")

@v1.get("/users")
async def list_users_v1():
    return await user_service.list(format="v1")

@v2.get("/users")
async def list_users_v2():
    return await user_service.list(format="v2")
```

## Deprecation

Mark deprecated endpoints:

```python
@v1.get("/users", deprecated=True)
async def list_users_v1():
    ...
```

Deprecated endpoints return a Deprecation header:
```
Deprecation: true
Sunset: 2025-01-01
Link: <https://api.example.com/v2/users>; rel="successor-version"
```

## Sunset Policy

- v(N-2) sunsets 6 months after v(N) release
- Breaking changes only in major versions
- Additive changes (new fields) allowed in minor versions

See [REST API](../sdks/rest-api.md) for current endpoints.
