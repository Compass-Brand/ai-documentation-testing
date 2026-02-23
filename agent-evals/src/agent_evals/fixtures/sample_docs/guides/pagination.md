# Pagination

Built-in pagination support for list endpoints.

## Cursor-Based Pagination

```python
from framework.pagination import CursorPaginator

@app.get("/api/products")
async def list_products(cursor: str = None, limit: int = 20):
    paginator = CursorPaginator(Product, limit=limit)
    return await paginator.paginate(cursor=cursor)
```

## Offset-Based Pagination

```python
from framework.pagination import OffsetPaginator

@app.get("/api/orders")
async def list_orders(page: int = 1, per_page: int = 25):
    paginator = OffsetPaginator(Order, per_page=per_page)
    return await paginator.paginate(page=page)
```

## Response Format

```json
{
  "data": [...],
  "pagination": {
    "next_cursor": "abc123",
    "has_more": true,
    "total": 150
  }
}
```

See [Users API](../api/users.md) for pagination examples in practice.
