# REST API Reference

Complete endpoint reference for the DataForge API.

## Base URL

```
https://api.example.com/v1
```

## Authentication

All requests require a Bearer token:

```
Authorization: Bearer <access_token>
```

## Endpoints

### Users

| Method | Path | Description |
|--------|------|-------------|
| GET | /users | List users |
| POST | /users | Create user |
| GET | /users/:id | Get user |
| PATCH | /users/:id | Update user |
| DELETE | /users/:id | Delete user |

### Products

| Method | Path | Description |
|--------|------|-------------|
| GET | /products | List products |
| POST | /products | Create product |
| GET | /products/:id | Get product |

## Rate Limiting

- 100 requests per minute per API key
- 429 response when exceeded
- Retry-After header indicates wait time

See [Error Handling](../api/errors.md) for error response format.
