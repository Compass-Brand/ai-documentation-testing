# Configuration

Application settings are loaded from environment variables with optional `.env` file support.

## Environment Variables

| Variable | Required | Default | Description |
|---|---|---|---|
| `DATABASE_URL` | Yes | -- | PostgreSQL connection string |
| `JWT_SECRET` | Yes | -- | Secret key for token signing |
| `LOG_LEVEL` | No | `INFO` | Logging verbosity |
| `CORS_ORIGINS` | No | `*` | Comma-separated allowed origins |
| `REDIS_URL` | No | -- | Cache backend URL |

## Loading Configuration

```python
from framework.config import Settings

settings = Settings()  # reads from environment
print(settings.database_url)
```

## Profiles

Use the `APP_PROFILE` variable to switch between configuration profiles:

```bash
export APP_PROFILE=development  # loads .env.development
export APP_PROFILE=production   # loads .env.production
```

Configuration validation runs at startup. Missing required variables raise `ConfigError` with a descriptive message. See [Deployment](deployment.md) for production environment setup.
