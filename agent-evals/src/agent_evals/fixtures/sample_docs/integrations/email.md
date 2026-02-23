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
