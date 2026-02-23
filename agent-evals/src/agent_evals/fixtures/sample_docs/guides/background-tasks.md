# Background Tasks

Running async background work in DataForge.

## Simple Tasks

```python
from framework.tasks import background_task

@background_task
async def send_welcome_email(user_id: int):
    user = await user_service.get(user_id)
    await email_service.send_template("welcome", user.email)
```

## Task Queues

For reliable task processing, use the Celery integration:

```python
from framework.tasks import celery_app

@celery_app.task(bind=True, max_retries=3)
def process_payment(self, order_id: int):
    try:
        payment_service.charge(order_id)
    except PaymentError as exc:
        self.retry(exc=exc, countdown=60)
```

## Scheduled Tasks

```python
from framework.tasks import scheduler

@scheduler.cron("0 */6 * * *")  # every 6 hours
async def cleanup_expired_tokens():
    await auth_service.purge_expired()
```

See [Deployment](../api/deployment.md) for worker configuration.
