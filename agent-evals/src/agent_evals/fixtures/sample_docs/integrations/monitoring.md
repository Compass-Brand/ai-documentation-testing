# Monitoring Integration

Application performance monitoring and alerting.

## Metrics Collection

```python
from framework.monitoring import metrics

@app.middleware("http")
async def track_requests(request, call_next):
    with metrics.timer("http_request_duration"):
        response = await call_next(request)
    metrics.increment("http_requests_total", tags={
        "method": request.method,
        "status": response.status_code,
    })
    return response
```

## Health Checks

```python
from framework.monitoring import health

health.register("database", check_db_connection)
health.register("redis", check_redis_connection)
health.register("storage", check_s3_access)
```

## Alerting

Configure alerts in monitoring.yaml:

```yaml
alerts:
  - name: high_error_rate
    condition: "rate(http_5xx) > 0.05"
    channel: slack
```

See [Logging](../api/logging.md) for structured log integration.
