# File Storage

Cloud and local file storage abstraction.

## Storage Backends

```python
from framework.storage import Storage, S3Backend, LocalBackend

# Production
storage = Storage(backend=S3Backend(
    bucket="my-app-files",
    region="us-east-1",
))

# Development
storage = Storage(backend=LocalBackend(path="./uploads"))
```

## Uploading Files

```python
@app.post("/api/files/upload")
async def upload_file(file: UploadFile):
    url = await storage.put(
        key=f"uploads/{file.filename}",
        data=await file.read(),
        content_type=file.content_type,
    )
    return {"url": url}
```

## Signed URLs

Generate time-limited access URLs:

```python
url = await storage.signed_url("uploads/report.pdf", expires=3600)
```

See [Configuration](../api/config.md) for AWS credential setup.
