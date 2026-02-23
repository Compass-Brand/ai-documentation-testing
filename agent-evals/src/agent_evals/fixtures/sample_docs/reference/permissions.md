# Permissions Reference

Role-based access control (RBAC) system.

## Built-in Roles

| Role | Description | Level |
|------|-------------|-------|
| admin | Full system access | 100 |
| manager | Team and resource management | 75 |
| editor | Content creation and editing | 50 |
| viewer | Read-only access | 25 |

## Permission Decorators

```python
from framework.auth import require_role, require_permission

@app.delete("/api/users/{id}")
@require_role("admin")
async def delete_user(id: int):
    await user_service.delete(id)

@app.patch("/api/posts/{id}")
@require_permission("posts.edit")
async def edit_post(id: int, data: EditPostRequest):
    return await post_service.update(id, data)
```

## Custom Permissions

```python
from framework.auth import Permission

class Permissions:
    MANAGE_USERS = Permission("users.manage")
    EDIT_POSTS = Permission("posts.edit")
    VIEW_REPORTS = Permission("reports.view")
```

See [Authentication](../api/auth.md) for token-based auth.
