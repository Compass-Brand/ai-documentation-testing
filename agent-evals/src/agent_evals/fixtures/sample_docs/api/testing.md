# Testing

The framework provides test utilities for writing reliable integration and unit tests.

## Test Client

Use `TestClient` for HTTP-level testing:

```python
from framework.testing import TestClient

client = TestClient(app)
response = client.get("/api/users")
assert response.status_code == 200
```

## Database Isolation

Each test runs in a transaction that rolls back after the test completes:

```python
import pytest
from framework.testing import db_session

@pytest.fixture
def session():
    with db_session() as s:
        yield s
    # automatic rollback
```

## Mocking External Services

```python
from unittest.mock import patch

@patch("framework.email.send_email")
def test_registration_sends_email(mock_send):
    client.post("/api/users", json={"email": "new@example.com", "name": "Test"})
    mock_send.assert_called_once()
```

## Running Tests

```bash
pytest tests/ -v --cov=framework --cov-report=term-missing
```

See [Database](database.md) for test database configuration and [Configuration](config.md) for test environment variables.
