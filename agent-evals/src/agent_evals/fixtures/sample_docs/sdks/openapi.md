# OpenAPI Specification

Auto-generated API documentation from code.

## Accessing Docs

- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc
- OpenAPI JSON: http://localhost:8000/openapi.json

## Customizing Docs

```python
from framework.docs import configure_docs

configure_docs(
    title="My API",
    version="2.0.0",
    description="Production API for MyApp",
)
```

## Adding Examples

```python
class CreateUserRequest(BaseModel):
    email: str
    name: str

    model_config = {
        "json_schema_extra": {
            "examples": [{
                "email": "alice@example.com",
                "name": "Alice",
            }]
        }
    }
```

See [REST API](rest-api.md) for endpoint reference.
