import uuid
from datetime import datetime

from app.core.celery_app import celery_app
from app.core.database import SessionLocal
from app.notifications.service import ReminderService


@celery_app.task(name="notifications.generate_reminder")
def generate_reminder(schedule_id: str, scheduled_for: str) -> str | None:
    with SessionLocal() as session:
        notification = ReminderService(session).generate(
            uuid.UUID(schedule_id), datetime.fromisoformat(scheduled_for)
        )
        return str(notification.id) if notification else None


@celery_app.task(name="notifications.dispatch_due_reminders")
def dispatch_due_reminders() -> int:
    with SessionLocal() as session:
        reminders = ReminderService(session).due_reminders()
    for reminder in reminders:
        generate_reminder.delay(str(reminder.schedule_id), reminder.scheduled_for.isoformat())
    return len(reminders)
