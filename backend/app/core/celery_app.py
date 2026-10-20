from celery import Celery

from app.core.config import get_settings

settings = get_settings()
celery_app = Celery(
    "nutrition_planner",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
    include=["app.notifications.tasks"],
)
celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
    beat_schedule={
        "dispatch-meal-reminders": {
            "task": "notifications.dispatch_due_reminders",
            "schedule": 60.0,
        }
    },
)
