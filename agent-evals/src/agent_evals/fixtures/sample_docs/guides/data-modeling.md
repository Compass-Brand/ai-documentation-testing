# Data Modeling

Design patterns for SQLAlchemy models in DataForge.

## Base Model

All models inherit from the framework base with automatic timestamps:

```python
from framework.database import Base, TimestampMixin

class Product(Base, TimestampMixin):
    __tablename__ = "products"
    id = Column(Integer, primary_key=True)
    name = Column(String(255), nullable=False)
    price = Column(Numeric(10, 2), nullable=False)
```

## Relationships

Use SQLAlchemy relationship patterns:

```python
class Order(Base):
    items = relationship("OrderItem", back_populates="order")

class OrderItem(Base):
    order_id = Column(ForeignKey("orders.id"))
    order = relationship("Order", back_populates="items")
```

## Soft Deletes

Enable soft deletes with the SoftDeleteMixin:

```python
class User(Base, SoftDeleteMixin):
    # adds deleted_at column, filters queries automatically
    pass
```

See [Database](../api/database.md) for connection setup and [Testing](../api/testing.md) for model tests.
