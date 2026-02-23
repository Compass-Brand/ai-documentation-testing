# Input Validation

Request validation using Pydantic models.

## Schema Definition

```python
from pydantic import BaseModel, EmailStr, Field

class CreateUserRequest(BaseModel):
    email: EmailStr
    name: str = Field(min_length=1, max_length=100)
    age: int = Field(ge=0, le=150)
```

## Automatic Validation

Route handlers with typed parameters validate automatically:

```python
@app.post("/api/users")
async def create_user(data: CreateUserRequest):
    # data is already validated
    return await user_service.create(data)
```

## Custom Validators

```python
from pydantic import field_validator

class TransferRequest(BaseModel):
    amount: float

    @field_validator("amount")
    @classmethod
    def amount_must_be_positive(cls, v):
        if v <= 0:
            raise ValueError("Amount must be positive")
        return v
```

See [Error Handling](../api/errors.md) for validation error response format.
