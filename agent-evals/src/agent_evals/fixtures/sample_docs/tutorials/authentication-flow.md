# Tutorial: Authentication Flow

Implement complete auth with login, registration, and password reset.

## Step 1: User Registration

```python
@app.post("/api/auth/register")
async def register(data: RegisterRequest):
    hashed = hash_password(data.password)
    user = await user_service.create(
        email=data.email, password_hash=hashed
    )
    token = create_access_token(user.id)
    return {"access_token": token}
```

## Step 2: Login

```python
@app.post("/api/auth/login")
async def login(data: LoginRequest):
    user = await user_service.authenticate(
        data.email, data.password
    )
    if not user:
        raise APIError(401, "INVALID_CREDENTIALS")
    return {"access_token": create_access_token(user.id)}
```

## Step 3: Password Reset

```python
@app.post("/api/auth/forgot-password")
async def forgot_password(data: ForgotPasswordRequest):
    token = await auth_service.create_reset_token(data.email)
    await send_email(data.email, "reset_password", {"token": token})
```

See [Authentication](../api/auth.md) for middleware details.
