# Tutorial: File Uploads

Handle file uploads with validation and cloud storage.

## Step 1: Upload Endpoint

```python
from fastapi import UploadFile

@app.post("/api/files")
async def upload(file: UploadFile):
    if file.size > 10_000_000:  # 10 MB limit
        raise APIError(413, "FILE_TOO_LARGE")

    key = f"uploads/{uuid4()}/{file.filename}"
    url = await storage.put(key, await file.read())
    return {"url": url, "filename": file.filename}
```

## Step 2: Image Processing

```python
from PIL import Image

async def create_thumbnail(file_key: str):
    data = await storage.get(file_key)
    img = Image.open(io.BytesIO(data))
    img.thumbnail((200, 200))
    thumb_key = file_key.replace("uploads/", "thumbs/")
    await storage.put(thumb_key, img_to_bytes(img))
```

## Step 3: Download

```python
@app.get("/api/files/{file_id}/download")
async def download(file_id: str):
    url = await storage.signed_url(f"uploads/{file_id}")
    return RedirectResponse(url)
```

See [Storage](../integrations/storage.md) for backend configuration.
