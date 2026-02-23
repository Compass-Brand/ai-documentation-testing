# Data Types Reference

Standard data types and serialization formats.

## Date and Time

All timestamps use ISO 8601 in UTC:

```json
{
  "created_at": "2024-03-15T14:30:00Z",
  "updated_at": "2024-03-15T14:30:00Z"
}
```

## IDs

Resources use integer IDs:

```json
{"id": 12345}
```

## Money

Monetary values use string representation to avoid floating-point issues:

```json
{"amount": "99.99", "currency": "USD"}
```

## Pagination

```json
{
  "data": [...],
  "meta": {
    "total": 150,
    "page": 1,
    "per_page": 25,
    "total_pages": 6
  }
}
```

## Enums

Enums are serialized as lowercase strings:

```json
{"status": "active", "role": "admin"}
```

See [REST API](../sdks/rest-api.md) for response schemas.
