# Database

The framework uses SQLAlchemy 2.0 with async support for all database operations.

## Connection Setup

```python
from framework.database import create_engine, SessionLocal

engine = create_engine(settings.database_url)
```

The connection pool defaults to 10 connections with a max overflow of 20. Adjust via `POOL_SIZE` and `MAX_OVERFLOW` environment variables.

## Models

Define ORM models by inheriting from `Base`:

```python
from framework.database import Base
from sqlalchemy import Column, Integer, String

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    email = Column(String, unique=True, nullable=False)
    name = Column(String, nullable=False)
```

## Migrations

Alembic manages schema migrations:

```bash
alembic revision --autogenerate -m "add users table"
alembic upgrade head
```

Run `alembic history` to view migration history. See [Configuration](config.md) for `DATABASE_URL` setup and [Testing](testing.md) for test database isolation.
