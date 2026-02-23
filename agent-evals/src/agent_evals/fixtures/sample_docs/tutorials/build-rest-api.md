# Tutorial: Build a REST API

Step-by-step guide to building a complete CRUD API.

## Step 1: Create Project

```bash
dataforge init todo-api
cd todo-api
```

## Step 2: Define Model

```python
# src/models/todo.py
from framework.database import Base
from sqlalchemy import Column, Integer, String, Boolean

class Todo(Base):
    __tablename__ = "todos"
    id = Column(Integer, primary_key=True)
    title = Column(String(200), nullable=False)
    completed = Column(Boolean, default=False)
```

## Step 3: Create Routes

```python
# src/routes/todos.py
@app.get("/api/todos")
async def list_todos():
    return await Todo.all()

@app.post("/api/todos")
async def create_todo(data: CreateTodoRequest):
    return await Todo.create(**data.model_dump())
```

## Step 4: Run and Test

```bash
dataforge db migrate
dataforge serve --reload
curl http://localhost:8000/api/todos
```

See [Database](../api/database.md) for model details and [Testing](../api/testing.md) for writing API tests.
