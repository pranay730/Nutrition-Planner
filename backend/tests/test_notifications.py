from collections.abc import Iterator
from datetime import UTC, datetime, time, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.main import create_app
from app.models import MealLog, MealSchedule, Notification, User
from app.models.enums import NotificationStatus
from app.notifications.service import ReminderService
from app.notifications.tasks import dispatch_due_reminders
from tests.helpers import make_profile, make_schedule, make_sqlite_session, make_user

PASSWORD = "correct horse battery staple"


def _reminder_session() -> tuple[Session, MealSchedule]:
    session = make_sqlite_session()
    user = make_user()
    profile = make_profile(user)
    profile.timezone = "America/Indiana/Indianapolis"
    schedule = make_schedule(user)
    schedule.preferred_time = time(12, 0)
    schedule.reminder_minutes_before = 15
    session.add(user)
    session.commit()
    return session, schedule


def test_due_reminders_respect_user_timezone_and_dst() -> None:
    session, schedule = _reminder_session()
    try:
        # Noon EDT is 16:00 UTC; the reminder is due at 15:45 UTC.
        due = ReminderService(session).due_reminders(
            now=datetime(2026, 7, 1, 15, 44, tzinfo=UTC), horizon=timedelta(minutes=2)
        )
        assert [(item.schedule_id, item.scheduled_for) for item in due] == [
            (schedule.id, datetime(2026, 7, 1, 15, 45, tzinfo=UTC))
        ]
    finally:
        session.close()


def test_due_reminders_skip_an_already_logged_meal() -> None:
    session, schedule = _reminder_session()
    try:
        session.add(
            MealLog(
                user_id=schedule.user_id,
                meal_type="lunch",
                food_name="Lunch",
                calories=500,
                occurred_at=datetime(2026, 7, 1, 15, 0, tzinfo=UTC),
            )
        )
        session.commit()

        assert ReminderService(session).due_reminders(
            now=datetime(2026, 7, 1, 15, 44, tzinfo=UTC), horizon=timedelta(minutes=2)
        ) == []
    finally:
        session.close()


def test_due_reminders_skip_disabled_schedules() -> None:
    session, schedule = _reminder_session()
    try:
        schedule.reminder_enabled = False
        session.commit()

        assert ReminderService(session).due_reminders(
            now=datetime(2026, 7, 1, 15, 44, tzinfo=UTC), horizon=timedelta(minutes=2)
        ) == []
    finally:
        session.close()


def test_generate_reminder_is_idempotent() -> None:
    session, schedule = _reminder_session()
    try:
        service = ReminderService(session)
        scheduled_for = datetime(2026, 7, 1, 15, 45, tzinfo=UTC)
        first = service.generate(schedule.id, scheduled_for)
        second = service.generate(schedule.id, scheduled_for)

        assert first is not None and second is not None
        assert first.id == second.id
        assert first.status == NotificationStatus.GENERATED
        assert session.scalar(select(func.count()).select_from(Notification)) == 1
    finally:
        session.close()


def test_generate_reminder_rechecks_meal_log_after_dispatch() -> None:
    session, schedule = _reminder_session()
    try:
        session.add(
            MealLog(
                user_id=schedule.user_id,
                meal_type=schedule.meal_type,
                food_name="Lunch",
                calories=500,
                occurred_at=datetime(2026, 7, 1, 15, 30, tzinfo=UTC),
            )
        )
        session.commit()

        notification = ReminderService(session).generate(
            schedule.id, datetime(2026, 7, 1, 15, 45, tzinfo=UTC)
        )

        assert notification is None
        assert session.scalar(select(func.count()).select_from(Notification)) == 0
    finally:
        session.close()


def test_dispatch_task_enqueues_each_due_reminder(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session, schedule = _reminder_session()
    schedule_id = str(schedule.id)
    scheduled_for = datetime(2026, 7, 1, 15, 45, tzinfo=UTC)
    queued: list[tuple[str, str]] = []
    monkeypatch.setattr("app.notifications.tasks.SessionLocal", lambda: session)
    monkeypatch.setattr(
        "app.notifications.service.utc_now",
        lambda: scheduled_for - timedelta(minutes=1),
    )
    monkeypatch.setattr(
        "app.notifications.tasks.generate_reminder.delay",
        lambda task_schedule_id, task_scheduled_for: queued.append(
            (task_schedule_id, task_scheduled_for)
        ),
    )

    count = dispatch_due_reminders.run()

    assert count == 1
    assert queued == [(schedule_id, scheduled_for.isoformat())]


@pytest.fixture
def notification_client() -> Iterator[tuple[TestClient, Session]]:
    session = make_sqlite_session()
    application = create_app()

    def override_database() -> Iterator[Session]:
        yield session

    application.dependency_overrides[get_db] = override_database
    with TestClient(application) as client:
        yield client, session
    session.close()


def _register(client: TestClient, email: str) -> dict[str, str]:
    response = client.post("/auth/register", json={"email": email, "password": PASSWORD})
    assert response.status_code == 201
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def test_notifications_are_owned_and_can_be_marked_read(
    notification_client: tuple[TestClient, Session], monkeypatch: pytest.MonkeyPatch
) -> None:
    client, session = notification_client
    owner_headers = _register(client, "owner@example.com")
    other_headers = _register(client, "other@example.com")
    owner_id = session.scalar(select(User.id).where(User.email == "owner@example.com"))
    notification = Notification(
        user_id=owner_id,
        meal_type="dinner",
        title="Dinner is coming up",
        body="Your planned dinner is coming up soon.",
        status=NotificationStatus.GENERATED,
        scheduled_for=datetime(2026, 10, 19, 21, 45, tzinfo=UTC),
        generated_at=datetime(2026, 10, 19, 21, 44, tzinfo=UTC),
    )
    session.add(notification)
    session.commit()
    session.refresh(notification)
    fixed_now = datetime(2026, 10, 19, 20, 0, tzinfo=UTC)
    monkeypatch.setattr("app.notifications.service.utc_now", lambda: fixed_now)

    assert client.get("/notifications", headers=other_headers).json() == {"notifications": []}
    hidden = client.patch(
        f"/notifications/{notification.id}", json={"read": True}, headers=other_headers
    )
    updated = client.patch(
        f"/notifications/{notification.id}", json={"read": True}, headers=owner_headers
    )

    assert hidden.status_code == 404
    assert updated.status_code == 200
    assert updated.json()["status"] == "read"
    assert datetime.fromisoformat(updated.json()["read_at"]).replace(tzinfo=UTC) == fixed_now
    assert client.get("/notifications?unread_only=true", headers=owner_headers).json() == {
        "notifications": []
    }


def test_notification_routes_require_authentication(
    notification_client: tuple[TestClient, Session],
) -> None:
    client, _ = notification_client
    assert client.get("/notifications").status_code == 401
