# Tutorial: Writing Tests

Comprehensive guide to testing DataForge applications.

## Unit Tests

```python
import pytest
from src.services.user_service import UserService

@pytest.fixture
def user_service(db_session):
    return UserService(db_session)

async def test_create_user(user_service):
    user = await user_service.create(
        email="test@example.com", name="Test"
    )
    assert user.email == "test@example.com"
    assert user.id is not None
```

## Integration Tests

```python
async def test_create_user_endpoint(client):
    response = await client.post("/api/users", json={
        "email": "new@example.com",
        "name": "New User",
    })
    assert response.status_code == 201
    assert response.json()["email"] == "new@example.com"
```

## Test Database

Each test gets an isolated database transaction that rolls back:

```python
@pytest.fixture
async def db_session():
    async with test_engine.begin() as conn:
        yield conn
        await conn.rollback()
```

See [Testing](../api/testing.md) for framework test utilities.
