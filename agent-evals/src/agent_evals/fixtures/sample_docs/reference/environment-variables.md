# Environment Variables Reference

Complete list of all configuration variables.

## Core

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| APP_NAME | No | DataForge | Application name |
| APP_ENV | No | development | Environment name |
| APP_DEBUG | No | false | Debug mode |
| APP_PORT | No | 8000 | Server port |
| APP_HOST | No | 0.0.0.0 | Server host |

## Database

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| DATABASE_URL | Yes | -- | PostgreSQL URL |
| POOL_SIZE | No | 10 | Connection pool size |
| MAX_OVERFLOW | No | 20 | Max overflow connections |

## Authentication

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| JWT_SECRET | Yes | -- | Token signing key |
| JWT_ALGORITHM | No | HS256 | Signing algorithm |
| JWT_EXPIRY | No | 3600 | Token TTL in seconds |

## Cache

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| REDIS_URL | No | -- | Redis connection URL |
| CACHE_TTL | No | 300 | Default cache TTL |

See [Configuration](../api/config.md) for loading behavior.
