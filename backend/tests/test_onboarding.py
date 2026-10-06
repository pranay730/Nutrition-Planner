from collections.abc import Iterator
from datetime import date, timedelta
from decimal import Decimal
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.main import create_app
from app.models import CuisinePreference, MealSchedule, Profile
from app.models.enums import ActivityLevel, CalculationSex, GoalType
from app.onboarding.schemas import ProfileUpdate
from app.onboarding.service import calculate_daily_calorie_target
from app.seed import seed_database
from tests.helpers import make_sqlite_session

PASSWORD = "correct horse battery staple"


@pytest.fixture
def onboarding_client() -> Iterator[tuple[TestClient, Session]]:
    session = make_sqlite_session()
    seed_database(session)
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


def profile_payload(**overrides: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "age": 30,
        "calculation_sex": "female",
        "height_cm": 170,
        "weight_kg": 70,
        "activity_level": "moderate",
        "goal_type": "maintain_weight",
        "timezone": "America/Indiana/Indianapolis",
    }
    payload.update(overrides)
    return payload


def test_calorie_target_uses_mifflin_st_jeor_and_activity_factor() -> None:
    data = ProfileUpdate(
        age=30,
        calculation_sex=CalculationSex.FEMALE,
        height_cm=Decimal("170"),
        weight_kg=Decimal("70"),
        activity_level=ActivityLevel.MODERATE,
        goal_type=GoalType.MAINTAIN,
        timezone="UTC",
    )

    assert calculate_daily_calorie_target(data) == 2250


def test_calorie_target_stays_within_persistence_bounds() -> None:
    data = ProfileUpdate(
        age=13,
        calculation_sex=CalculationSex.MALE,
        height_cm=Decimal("250"),
        weight_kg=Decimal("499"),
        activity_level=ActivityLevel.VERY_ACTIVE,
        goal_type=GoalType.GAIN,
        goal_weight_kg=Decimal("500"),
        target_date=date.today() + timedelta(days=30),
        timezone="UTC",
    )

    assert calculate_daily_calorie_target(data) == 10000


def test_profile_is_upserted_for_token_owner(
    onboarding_client: tuple[TestClient, Session],
) -> None:
    client, session = onboarding_client
    first = register(client, "first@example.com")
    second = register(client, "second@example.com")

    first_response = client.put(
        "/onboarding/profile", json=profile_payload(), headers=headers(first["access_token"])
    )
    second_response = client.put(
        "/onboarding/profile",
        json=profile_payload(age=40, activity_level="light"),
        headers=headers(second["access_token"]),
    )
    update = client.put(
        "/onboarding/profile",
        json=profile_payload(weight_kg=68),
        headers=headers(first["access_token"]),
    )

    assert first_response.status_code == second_response.status_code == update.status_code == 200
    assert first_response.json()["daily_calorie_target"] == 2250
    assert update.json()["weight_kg"] == "68.00"
    assert session.scalar(select(func.count()).select_from(Profile)) == 2


@pytest.mark.parametrize(
    "payload",
    [
        profile_payload(timezone="Not/A_Timezone"),
        profile_payload(
            goal_type="lose_weight",
            goal_weight_kg=75,
            target_date=str(date.today() + timedelta(days=30)),
        ),
        profile_payload(goal_type="gain_weight", goal_weight_kg=75),
    ],
)
def test_profile_rejects_invalid_timezone_or_goal(
    onboarding_client: tuple[TestClient, Session], payload: dict[str, Any]
) -> None:
    client, _ = onboarding_client
    auth = register(client)

    response = client.put(
        "/onboarding/profile", json=payload, headers=headers(auth["access_token"])
    )

    assert response.status_code == 422


def test_cuisine_preferences_are_canonical_and_replace_existing_values(
    onboarding_client: tuple[TestClient, Session],
) -> None:
    client, session = onboarding_client
    auth = register(client)
    auth_headers = headers(auth["access_token"])

    first = client.put(
        "/preferences/cuisines",
        json={"cuisines": ["indian", "ITALIAN"]},
        headers=auth_headers,
    )
    second = client.put(
        "/preferences/cuisines", json={"cuisines": ["Thai"]}, headers=auth_headers
    )

    assert first.status_code == second.status_code == 200
    assert first.json() == {"cuisines": ["Indian", "Italian"]}
    assert second.json() == {"cuisines": ["Thai"]}
    assert session.scalars(select(CuisinePreference.cuisine)).all() == ["Thai"]

    cleared = client.put(
        "/preferences/cuisines", json={"cuisines": []}, headers=auth_headers
    )

    assert cleared.status_code == 200
    assert cleared.json() == {"cuisines": []}
    assert session.scalar(select(func.count()).select_from(CuisinePreference)) == 0


def test_unknown_cuisine_is_rejected(onboarding_client: tuple[TestClient, Session]) -> None:
    client, _ = onboarding_client
    auth = register(client)

    response = client.put(
        "/preferences/cuisines",
        json={"cuisines": ["Martian"]},
        headers=headers(auth["access_token"]),
    )

    assert response.status_code == 422
    assert response.json()["detail"] == "Unknown cuisines: Martian"


def test_ingredient_suggestions_adapt_to_cuisine_preferences(
    onboarding_client: tuple[TestClient, Session],
) -> None:
    client, _ = onboarding_client
    auth = register(client)
    auth_headers = headers(auth["access_token"])
    client.put(
        "/preferences/cuisines",
        json={"cuisines": ["Indian", "Italian"]},
        headers=auth_headers,
    )

    response = client.get("/ingredients/suggestions?limit=10", headers=auth_headers)

    assert response.status_code == 200
    suggestions = response.json()
    assert suggestions
    assert suggestions[0]["matching_cuisines"] == ["Indian", "Italian"]
    assert all(item["matching_cuisines"] for item in suggestions)


def test_meal_schedules_are_upserted_and_replaced(
    onboarding_client: tuple[TestClient, Session],
) -> None:
    client, session = onboarding_client
    auth = register(client)
    auth_headers = headers(auth["access_token"])
    first_payload = {
        "schedules": [
            {"meal_type": "Breakfast", "preferred_time": "08:00:00"},
            {
                "meal_type": "dinner",
                "preferred_time": "18:30:00",
                "reminder_minutes_before": 30,
            },
        ]
    }

    first = client.put("/meal-schedules", json=first_payload, headers=auth_headers)
    second = client.put(
        "/meal-schedules",
        json={
            "schedules": [
                {
                    "meal_type": "dinner",
                    "preferred_time": "19:00:00",
                    "reminder_enabled": False,
                }
            ]
        },
        headers=auth_headers,
    )

    assert first.status_code == second.status_code == 200
    assert [item["meal_type"] for item in first.json()["schedules"]] == ["breakfast", "dinner"]
    assert second.json()["schedules"] == [
        {
            "meal_type": "dinner",
            "preferred_time": "19:00:00",
            "reminder_minutes_before": 15,
            "reminder_enabled": False,
        }
    ]
    assert session.scalar(select(func.count()).select_from(MealSchedule)) == 1

    cleared = client.put("/meal-schedules", json={"schedules": []}, headers=auth_headers)

    assert cleared.status_code == 200
    assert cleared.json() == {"schedules": []}
    assert session.scalar(select(func.count()).select_from(MealSchedule)) == 0


def test_meal_schedule_rejects_blank_meal_type(
    onboarding_client: tuple[TestClient, Session],
) -> None:
    client, _ = onboarding_client
    auth = register(client)

    response = client.put(
        "/meal-schedules",
        json={"schedules": [{"meal_type": "   ", "preferred_time": "12:00:00"}]},
        headers=headers(auth["access_token"]),
    )

    assert response.status_code == 422


def test_preferences_suggestions_and_schedules_are_isolated_by_user(
    onboarding_client: tuple[TestClient, Session],
) -> None:
    client, session = onboarding_client
    first = register(client, "first@example.com")
    second = register(client, "second@example.com")
    first_headers = headers(first["access_token"])
    second_headers = headers(second["access_token"])

    client.put(
        "/preferences/cuisines", json={"cuisines": ["Indian"]}, headers=first_headers
    )
    client.put(
        "/preferences/cuisines", json={"cuisines": ["Italian"]}, headers=second_headers
    )
    client.put(
        "/meal-schedules",
        json={"schedules": [{"meal_type": "breakfast", "preferred_time": "08:00:00"}]},
        headers=first_headers,
    )
    client.put(
        "/meal-schedules",
        json={"schedules": [{"meal_type": "dinner", "preferred_time": "19:00:00"}]},
        headers=second_headers,
    )

    first_suggestions = client.get("/ingredients/suggestions", headers=first_headers).json()
    second_suggestions = client.get("/ingredients/suggestions", headers=second_headers).json()

    assert all("Indian" in item["matching_cuisines"] for item in first_suggestions)
    assert all("Italian" in item["matching_cuisines"] for item in second_suggestions)
    assert session.scalar(select(func.count()).select_from(CuisinePreference)) == 2
    assert session.scalar(select(func.count()).select_from(MealSchedule)) == 2


@pytest.mark.parametrize(
    ("method", "path", "json"),
    [
        ("put", "/onboarding/profile", profile_payload()),
        ("put", "/preferences/cuisines", {"cuisines": ["Indian"]}),
        (
            "put",
            "/meal-schedules",
            {"schedules": [{"meal_type": "lunch", "preferred_time": "12:00:00"}]},
        ),
        ("get", "/ingredients/suggestions", None),
    ],
)
def test_phase_four_routes_require_authentication(
    onboarding_client: tuple[TestClient, Session], method: str, path: str, json: object
) -> None:
    client, _ = onboarding_client

    response = client.request(method, path, json=json)

    assert response.status_code == 401
