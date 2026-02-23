# Search Integration

Full-text search with Elasticsearch or Meilisearch.

## Configuration

```python
SEARCH_BACKEND=meilisearch
MEILISEARCH_URL=http://localhost:7700
MEILISEARCH_API_KEY=masterKey
```

## Indexing Documents

```python
from framework.search import SearchIndex

index = SearchIndex("products")
await index.add_documents([
    {"id": 1, "name": "Widget", "description": "A useful widget"},
    {"id": 2, "name": "Gadget", "description": "A handy gadget"},
])
```

## Searching

```python
results = await index.search("widget", filters={"category": "tools"})
for hit in results.hits:
    print(hit.name, hit.score)
```

See [Database](../api/database.md) for keeping search indexes in sync with models.
