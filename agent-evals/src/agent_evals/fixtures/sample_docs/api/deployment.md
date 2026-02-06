# Deployment

Production deployment guide for the framework application.

## Docker

Build and run using the provided Dockerfile:

```bash
docker build -t myapp:latest .
docker run -p 8000:8000 --env-file .env.production myapp:latest
```

The image uses a multi-stage build to keep the final size under 150 MB.

## Docker Compose

For local multi-service development:

```yaml
services:
  app:
    build: .
    ports:
      - "8000:8000"
    depends_on:
      - db
      - redis
  db:
    image: postgres:16
    environment:
      POSTGRES_DB: myapp
      POSTGRES_PASSWORD: localdev
  redis:
    image: redis:7-alpine
```

## CI/CD Pipeline

The GitHub Actions workflow handles:

1. Run linting and type checks
2. Execute test suite with coverage
3. Build Docker image
4. Push to container registry
5. Deploy to staging (on `develop` branch)
6. Deploy to production (on `main` branch, manual approval required)

## Health Check

The `/health` endpoint returns service status:

```bash
curl http://localhost:8000/health
```

See [Configuration](config.md) for environment variable reference and [Database](database.md) for migration steps before deployment.
