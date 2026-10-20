import uuid
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload

from app.models import MealLog, MealSchedule, Notification, Profile, User
from app.models.enums import NotificationStatus


def utc_now() -> datetime:
    return datetime.now(UTC)


@dataclass(frozen=True)
class DueReminder:
    schedule_id: uuid.UUID
    scheduled_for: datetime


def _reminder_time(schedule: MealSchedule, local_date: date, timezone: ZoneInfo) -> datetime:
    meal_time = datetime.combine(local_date, schedule.preferred_time, tzinfo=timezone)
    return (meal_time - timedelta(minutes=schedule.reminder_minutes_before)).astimezone(UTC)


class ReminderService:
    def __init__(self, session: Session) -> None:
        self.session = session

    def due_reminders(
        self, *, now: datetime | None = None, horizon: timedelta = timedelta(minutes=5)
    ) -> list[DueReminder]:
        start = (now or utc_now()).astimezone(UTC)
        end = start + horizon
        schedules = self.session.scalars(
            select(MealSchedule)
            .join(MealSchedule.user)
            .join(Profile, Profile.user_id == MealSchedule.user_id)
            .options(joinedload(MealSchedule.user).joinedload(User.profile))
            .where(MealSchedule.reminder_enabled.is_(True))
        ).all()
        due: list[DueReminder] = []
        for schedule in schedules:
            timezone = ZoneInfo(schedule.user.profile.timezone)
            local_start = start.astimezone(timezone).date()
            for candidate_date in (local_start, local_start + timedelta(days=1)):
                scheduled_for = _reminder_time(schedule, candidate_date, timezone)
                if not start <= scheduled_for < end:
                    continue
                if self._meal_already_logged(schedule, candidate_date, timezone):
                    continue
                due.append(DueReminder(schedule.id, scheduled_for))
        return sorted(due, key=lambda item: (item.scheduled_for, str(item.schedule_id)))

    def _meal_already_logged(
        self, schedule: MealSchedule, local_date: date, timezone: ZoneInfo
    ) -> bool:
        day_start = datetime.combine(local_date, time.min, tzinfo=timezone).astimezone(UTC)
        day_end = datetime.combine(
            local_date + timedelta(days=1), time.min, tzinfo=timezone
        ).astimezone(UTC)
        return (
            self.session.scalar(
                select(MealLog.id).where(
                    MealLog.user_id == schedule.user_id,
                    MealLog.meal_type == schedule.meal_type,
                    MealLog.occurred_at >= day_start,
                    MealLog.occurred_at < day_end,
                )
            )
            is not None
        )

    def generate(self, schedule_id: uuid.UUID, scheduled_for: datetime) -> Notification | None:
        schedule = self.session.scalar(
            select(MealSchedule)
            .options(joinedload(MealSchedule.user).joinedload(User.profile))
            .where(MealSchedule.id == schedule_id, MealSchedule.reminder_enabled.is_(True))
        )
        if schedule is None or schedule.user.profile is None:
            return None
        scheduled_for = scheduled_for.astimezone(UTC)
        timezone = ZoneInfo(schedule.user.profile.timezone)
        meal_datetime = scheduled_for + timedelta(minutes=schedule.reminder_minutes_before)
        meal_date = meal_datetime.astimezone(timezone).date()
        if self._meal_already_logged(schedule, meal_date, timezone):
            return None
        meal_name = schedule.meal_type.replace("_", " ").title()
        notification = Notification(
            user_id=schedule.user_id,
            meal_type=schedule.meal_type,
            title=f"{meal_name} is coming up",
            body=f"Your planned {schedule.meal_type.replace('_', ' ')} is coming up soon.",
            status=NotificationStatus.GENERATED,
            scheduled_for=scheduled_for,
            generated_at=utc_now(),
        )
        self.session.add(notification)
        try:
            self.session.commit()
        except IntegrityError:
            self.session.rollback()
            return self.session.scalar(
                select(Notification).where(
                    Notification.user_id == schedule.user_id,
                    Notification.meal_type == schedule.meal_type,
                    Notification.scheduled_for == scheduled_for,
                )
            )
        self.session.refresh(notification)
        return notification

    def list_for_user(
        self, user_id: uuid.UUID, *, unread_only: bool = False, limit: int = 50
    ) -> list[Notification]:
        statement = select(Notification).where(Notification.user_id == user_id)
        if unread_only:
            statement = statement.where(Notification.read_at.is_(None))
        return list(
            self.session.scalars(
                statement.order_by(Notification.generated_at.desc(), Notification.id.desc()).limit(
                    limit
                )
            )
        )

    def set_read(
        self, user_id: uuid.UUID, notification_id: uuid.UUID, *, read: bool
    ) -> Notification | None:
        notification = self.session.scalar(
            select(Notification).where(
                Notification.id == notification_id, Notification.user_id == user_id
            )
        )
        if notification is None:
            return None
        notification.read_at = utc_now() if read else None
        notification.status = NotificationStatus.READ if read else NotificationStatus.GENERATED
        self.session.commit()
        self.session.refresh(notification)
        return notification
