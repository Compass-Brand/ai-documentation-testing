# Notifications

Multi-channel notification delivery.

## Channels

- Email (SendGrid, SES)
- SMS (Twilio)
- Push (Firebase Cloud Messaging)
- In-app (WebSocket)

## Sending Notifications

```python
from framework.notifications import notify

await notify(
    user_id=123,
    template="order_shipped",
    channels=["email", "push"],
    context={"tracking_number": "1Z999AA10123456784"},
)
```

## Notification Preferences

Users control which channels they receive on:

```python
prefs = await notification_service.get_preferences(user_id=123)
# {"email": True, "sms": False, "push": True}
```

See [Email](email.md) for email-specific configuration.
