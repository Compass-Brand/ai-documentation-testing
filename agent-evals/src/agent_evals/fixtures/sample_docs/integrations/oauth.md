# OAuth Integration

Social login and OAuth2 provider support.

## Supported Providers

- Google
- GitHub
- Microsoft Azure AD
- Custom OIDC

## Configuration

```python
OAUTH_GOOGLE_CLIENT_ID=xxx.apps.googleusercontent.com
OAUTH_GOOGLE_CLIENT_SECRET=xxx
OAUTH_GITHUB_CLIENT_ID=xxx
OAUTH_GITHUB_CLIENT_SECRET=xxx
```

## Login Flow

```python
from framework.oauth import OAuthRouter

oauth = OAuthRouter()

@oauth.login("google")
async def google_callback(user_info):
    user = await user_service.find_or_create(
        email=user_info.email,
        provider="google",
    )
    return create_session(user)
```

See [Authentication](../api/auth.md) for JWT integration with OAuth.
