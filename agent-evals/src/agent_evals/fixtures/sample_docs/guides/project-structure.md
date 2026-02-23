# Project Structure

Standard DataForge project layout and file organization.

## Directory Layout

```
my-project/
├── src/
│   ├── models/       # ORM models
│   ├── routes/       # API endpoint handlers
│   ├── services/     # Business logic
│   ├── middleware/    # Request/response middleware
│   └── utils/        # Shared utilities
├── tests/
│   ├── unit/         # Unit tests
│   └── integration/  # Integration tests
├── migrations/       # Alembic database migrations
├── config/           # Configuration profiles
└── pyproject.toml    # Project metadata
```

## Naming Conventions

- Models: singular PascalCase (e.g. User, OrderItem)
- Routes: plural lowercase (e.g. users.py, orders.py)
- Services: singular with suffix (e.g. user_service.py)

See [Architecture](../repo/architecture.md) for design philosophy.
