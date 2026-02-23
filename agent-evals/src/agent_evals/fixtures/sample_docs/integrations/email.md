# Email Integration

Sending transactional emails from DataForge.

## Configuration

```python
EMAIL_PROVIDER=sendgrid
SENDGRID_API_KEY=SG.xxx
EMAIL_FROM=noreply@example.com
```

## Sending Emails

```python
from framework.email import send_email

await send_email(
    to="user@example.com",
    subject="Welcome!",
    template="welcome",
    context={"name": "Alice"},
)
```

## Templates

Email templates use Jinja2 and live in templates/email/:

```html
<h1>Welcome, {{ name }}!</h1>
<p>Your account has been created.</p>
```

See [Configuration](../api/config.md) for email provider settings.
