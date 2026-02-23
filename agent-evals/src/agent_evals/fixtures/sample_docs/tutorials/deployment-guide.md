# Tutorial: Production Deployment

Deploy DataForge to production with Docker and CI/CD.

## Step 1: Dockerfile

```dockerfile
FROM python:3.12-slim as builder
WORKDIR /app
COPY pyproject.toml .
RUN pip install --no-cache-dir .

FROM python:3.12-slim
COPY --from=builder /usr/local/lib/python3.12 /usr/local/lib/python3.12
COPY src/ /app/src/
CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0"]
```

## Step 2: Environment

Create .env.production with production values:

```
DATABASE_URL=postgresql://prod_user:xxx@db.host/myapp
JWT_SECRET=<generated-secret>
LOG_LEVEL=WARNING
```

## Step 3: Database Migration

```bash
dataforge db migrate --env production
```

## Step 4: Health Checks

Verify deployment:

```bash
curl https://api.example.com/health
# {"status": "ok", "database": "connected", "cache": "connected"}
```

See [Deployment](../api/deployment.md) for Docker Compose and CI/CD details.
