# Users API

CRUD endpoints for user management. All endpoints require authentication unless noted.

## Endpoints

### List Users

```
GET /api/users?page=1&per_page=20&role=admin
```

Query parameters:

- `page` (int): Page number, default 1
- `per_page` (int): Items per page, default 20, max 100
- `role` (str, optional): Filter by role name
- `search` (str, optional): Full-text search on name and email

### Create User

```
POST /api/users
```

```json
{
  "email": "user@example.com",
  "name": "Jane Doe",
  "role": "editor"
}
```

### Get User

```
GET /api/users/{user_id}
```

### Update User

```
PATCH /api/users/{user_id}
```

### Delete User

```
DELETE /api/users/{user_id}
```

Requires the `admin` role. See [Authentication](auth.md) for role checks and [Error Handling](errors.md) for status codes.
