# Python SDK

Official Python client for the DataForge API.

## Installation

```bash
pip install dataforge-sdk
```

## Authentication

```python
from dataforge import Client

client = Client(
    base_url="https://api.example.com",
    api_key="df_live_xxx",
)
```

## Usage Examples

```python
# List users
users = client.users.list(page=1, per_page=10)

# Create a user
user = client.users.create(
    email="alice@example.com",
    name="Alice",
)

# Get user by ID
user = client.users.get(user_id=123)
```

## Error Handling

```python
from dataforge.exceptions import APIError, RateLimitError

try:
    client.users.create(email="duplicate@example.com")
except RateLimitError:
    time.sleep(60)
except APIError as e:
    print(f"Error {e.code}: {e.message}")
```

See [Users API](../api/users.md) for endpoint details.
