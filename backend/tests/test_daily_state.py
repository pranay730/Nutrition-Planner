from collections.abc import Iterator
from datetime import UTC, datetime, time, timedelta
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.main import create_app
from app.meals.schemas import MealCreate
from app.meals.service import (
    DailyStateService,
    FutureMealError,
    allocate_calories,
    local_day_bounds,
)
from app.models import MealLog
from tests.helpers import make_profile, make_schedule, make_sqlite_session, make_user

PASSWORD = "correct horse battery staple"


@pytest.fixture
def daily_client() -> Iterator[tuple[TestClient, Session]]:
    session = make_sqlite_session()
    application = create_app()

    def override_database() -> Iterator[Session]:
        yield session

    application.dependency_overrides[get_db] = override_database
    with TestClient(application) as client:
        yield client, session
    session.close()


def register(client: TestClient, email: str = "pat@example.com") -> dict[str, Any]:
    response = client.post("/auth/register", json={"email": email, "password": PASSWORD})
    assert response.status_code == 201
    return response.json()


def headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def onboard(client: TestClient, auth_headers: dict[str, str], timezone: str = "UTC") -> None:
    response = client.put(
        "/onboarding/profile",
        headers=auth_headers,
        json={
            "age": 30,
            "calculation_sex": "female",
            "height_cm": 170,
            "weight_kg": 70,
            "activity_level": "moderate",
            "goal_type": "maintain_weight",
            "timezone": timezone,
        },
    )
    assert response.status_code == 200


def test_local_day_bounds_follow_dst_transition() -> None:
    now = datetime(2026, 3, 8, 16, tzinfo=UTC)

    local_date, start, end = local_day_bounds(now, "America/New_York")

    assert local_date.isoformat() == "2026-03-08"
    assert start == datetime(2026, 3, 8, 5, tzinfo=UTC)
    assert end == datetime(2026, 3, 9, 4, tzinfo=UTC)
    assert end - start == timedelta(hours=23)


def test_local_day_bounds_follow_dst_fall_back_transition() -> None:
    now = datetime(2026, 11, 1, 17, tzinfo=UTC)

    local_date, start, end = local_day_bounds(now, "America/New_York")

    assert local_date.isoformat() == "2026-11-01"
    assert start == datetime(2026, 11, 1, 4, tzinfo=UTC)
    assert end == datetime(2026, 11, 2, 5, tzinfo=UTC)
    assert end - start == timedelta(hours=25)


def test_today_uses_profile_timezone_boundaries() -> None:
    user = make_user()
    profile = make_profile(user)
    profile.timezone = "America/New_York"
    now = datetime(2026, 3, 8, 16, tzinfo=UTC)
    included = [
        MealLog(
            user=user,
            meal_type="breakfast",
            calories=300,
            occurred_at=datetime(2026, 3, 8, 5, tzinfo=UTC),
        ),
        MealLog(
            user=user,
            meal_type="dinner",
            calories=700,
            occurred_at=datetime(2026, 3, 9, 3, 59, tzinfo=UTC),
        ),
    ]
    excluded = [
        MealLog(
            user=user,
            meal_type="late",
            calories=200,
            occurred_at=datetime(2026, 3, 8, 4, 59, tzinfo=UTC),
        ),
        MealLog(
            user=user,
            meal_type="next",
            calories=400,
            occurred_at=datetime(2026, 3, 9, 4, tzinfo=UTC),
        ),
    ]

    with make_sqlite_session() as session:
        session.add_all([user, *included, *excluded])
        session.commit()

        local_date, timezone, meals = DailyStateService(session).meals_today(user, now=now)

        assert local_date.isoformat() == "2026-03-08"
        assert timezone == "America/New_York"
        assert [meal.calories for meal in meals] == [300, 700]


def test_allocation_is_exact_and_deterministic() -> None:
    allocations = allocate_calories(
        1000,
        [("lunch", time(12)), ("snack", time(15)), ("dinner", time(19))],
    )

    assert [item.allocated_calories for item in allocations] == [334, 333, 333]
    assert sum(item.allocated_calories for item in allocations) == 1000


def test_daily_plan_allocates_to_upcoming_unlogged_meals() -> None:
    user = make_user()
    make_profile(user, daily_calorie_target=2000)
    make_schedule(user, "breakfast").preferred_time = time(8)
    make_schedule(user, "lunch").preferred_time = time(13)
    make_schedule(user, "dinner").preferred_time = time(19)
    now = datetime(2026, 1, 15, 17, tzinfo=UTC)
    lunch = MealLog(
        user=user,
        meal_type="lunch",
        calories=600,
        occurred_at=datetime(2026, 1, 15, 16, tzinfo=UTC),
    )

    with make_sqlite_session() as session:
        session.add_all([user, lunch])
        session.commit()

        plan = DailyStateService(session).daily_plan(user, now=now)

        assert plan.consumed_calories == 600
        assert plan.remaining_calories == 1400
        assert [(item.meal_type, item.allocated_calories) for item in plan.allocations] == [
            ("dinner", 1400)
        ]


def test_over_target_plan_reports_deficit_and_allocates_zero() -> None:
    user = make_user()
    make_profile(user, daily_calorie_target=1200)
    make_schedule(user, "dinner").preferred_time = time(19)
    meal = MealLog(
        user=user,
        meal_type="lunch",
        calories=1500,
        occurred_at=datetime(2026, 1, 15, 16, tzinfo=UTC),
    )

    with make_sqlite_session() as session:
        session.add_all([user, meal])
        session.commit()

        plan = DailyStateService(session).daily_plan(
            user, now=datetime(2026, 1, 15, 17, tzinfo=UTC)
        )

        assert plan.remaining_calories == -300
        assert plan.allocations[0].allocated_calories == 0


def test_create_meal_rejects_future_timestamp() -> None:
    user = make_user()
    now = datetime(2026, 1, 15, 17, tzinfo=UTC)
    payload = MealCreate(
        meal_type="lunch", calories=500, occurred_at=now + timedelta(minutes=6)
    )

    with make_sqlite_session() as session, pytest.raises(FutureMealError):
        session.add(user)
        session.commit()
        DailyStateService(session).create_meal(user, payload, now=now)


def test_meal_api_logs_and_lists_only_token_owners_meals(
    daily_client: tuple[TestClient, Session],
) -> None:
    client, _ = daily_client
    first = register(client, "first@example.com")
    second = register(client, "second@example.com")
    first_headers = headers(first["access_token"])
    second_headers = headers(second["access_token"])
    onboard(client, first_headers)
    onboard(client, second_headers)

    first_meal = client.post(
        "/meals",
        headers=first_headers,
        json={"meal_type": "Lunch", "food_name": "Rice bowl", "calories": 550},
    )
    second_meal = client.post(
        "/meals",
        headers=second_headers,
        json={"meal_type": "dinner", "food_name": "Pasta", "calories": 700},
    )
    first_today = client.get("/meals/today", headers=first_headers)
    second_today = client.get("/meals/today", headers=second_headers)

    assert first_meal.status_code == second_meal.status_code == 201
    assert first_meal.json()["meal_type"] == "lunch"
    assert first_meal.json()["occurred_at"].endswith("Z")
    assert first_today.json()["total_calories"] == 550
    assert [meal["food_name"] for meal in first_today.json()["meals"]] == ["Rice bowl"]
    assert second_today.json()["total_calories"] == 700
    assert [meal["food_name"] for meal in second_today.json()["meals"]] == ["Pasta"]


def test_meal_api_rejects_naive_timestamp(daily_client: tuple[TestClient, Session]) -> None:
    client, _ = daily_client
    auth = register(client)

    response = client.post(
        "/meals",
        headers=headers(auth["access_token"]),
        json={
            "meal_type": "lunch",
            "calories": 500,
            "occurred_at": "2026-01-15T16:00:00",
        },
    )

    assert response.status_code == 422


def test_daily_plan_api_returns_exact_upcoming_allocations(
    daily_client: tuple[TestClient, Session], monkeypatch: pytest.MonkeyPatch
) -> None:
    fixed_now = datetime(2026, 1, 15, 17, tzinfo=UTC)
    monkeypatch.setattr("app.meals.service.utc_now", lambda: fixed_now)
    client, _ = daily_client
    auth = register(client)
    auth_headers = headers(auth["access_token"])
    onboard(client, auth_headers)
    schedules = client.put(
        "/meal-schedules",
        headers=auth_headers,
        json={
            "schedules": [
                {"meal_type": "dinner", "preferred_time": "18:00:00"},
                {"meal_type": "snack", "preferred_time": "20:00:00"},
            ]
        },
    )
    meal = client.post(
        "/meals",
        headers=auth_headers,
        json={
            "meal_type": "lunch",
            "calories": 500,
            "occurred_at": "2026-01-15T16:00:00Z",
        },
    )

    response = client.get("/daily-plan", headers=auth_headers)

    assert schedules.status_code == 200
    assert meal.status_code == 201
    assert response.status_code == 200
    assert response.json() == {
        "date": "2026-01-15",
        "timezone": "UTC",
        "calorie_target": 2250,
        "consumed_calories": 500,
        "remaining_calories": 1750,
        "allocations": [
            {
                "meal_type": "dinner",
                "scheduled_time": "18:00:00",
                "allocated_calories": 875,
            },
            {
                "meal_type": "snack",
                "scheduled_time": "20:00:00",
                "allocated_calories": 875,
            },
        ],
    }


def test_daily_state_requires_profile(daily_client: tuple[TestClient, Session]) -> None:
    client, _ = daily_client
    auth = register(client)
    auth_headers = headers(auth["access_token"])

    meals = client.get("/meals/today", headers=auth_headers)
    plan = client.get("/daily-plan", headers=auth_headers)

    assert meals.status_code == plan.status_code == 409


@pytest.mark.parametrize(
    ("method", "path", "json"),
    [
        ("post", "/meals", {"meal_type": "lunch", "calories": 500}),
        ("get", "/meals/today", None),
        ("get", "/daily-plan", None),
    ],
)
def test_daily_state_routes_require_authentication(
    daily_client: tuple[TestClient, Session], method: str, path: str, json: object
) -> None:
    client, _ = daily_client

    response = client.request(method, path, json=json)

    assert response.status_code == 401
