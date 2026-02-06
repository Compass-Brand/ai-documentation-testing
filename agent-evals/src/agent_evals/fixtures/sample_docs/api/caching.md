# Caching

The framework supports response caching with Redis or in-memory backends.

## Cache Configuration

```python
from framework.cache import CacheConfig, RedisBackend

cache = CacheConfig(
    backend=RedisBackend(url=settings.redis_url),
    default_ttl=300,  # 5 minutes
)
app.configure_cache(cache)
```

## Caching Responses

Decorate endpoints with `@cached` to store responses:

```python
@app.get("/api/reports/summary")
@cached(ttl=600)
async def get_report_summary():
    return await generate_summary()  # expensive operation
```

## Cache Invalidation

Invalidate specific keys or patterns:

```python
from framework.cache import invalidate

await invalidate("reports:summary")        # single key
await invalidate("users:*")               # pattern-based
await invalidate(tags=["user-profiles"])   # tag-based
```

## Cache Strategies

- **TTL-based** -- Entries expire after a fixed duration
- **LRU** -- Least recently used eviction when cache is full
- **Write-through** -- Cache updates on every write operation

The in-memory backend is suitable for development. Use Redis for production deployments with multiple workers. See [Configuration](config.md) for `REDIS_URL` setup and [Middleware](middleware.md) for cache headers.
