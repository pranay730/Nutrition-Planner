import uuid
from collections.abc import Iterator
from datetime import UTC, datetime, time
from decimal import Decimal
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.main import create_app
from app.models import Ingredient, MealLog, PantryItem, Recipe, RecipeIngredient
from app.models.enums import PantryStatus
from app.recommendations.service import RecommendationService, ScoringContext, score_recipe
from app.seed import seed_database
from tests.helpers import (
    make_cuisine_preference,
    make_profile,
    make_schedule,
    make_sqlite_session,
    make_user,
)

PASSWORD = "correct horse battery staple"


@pytest.fixture
def recommendation_client() -> Iterator[tuple[TestClient, Session]]:
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


def onboard(client: TestClient, auth_headers: dict[str, str]) -> None:
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
            "timezone": "UTC",
        },
    )
    assert response.status_code == 200


def make_recipe() -> tuple[Recipe, Ingredient, Ingredient]:
    rice = Ingredient(id=uuid.uuid4(), name="rice", category="grains")
    tofu = Ingredient(id=uuid.uuid4(), name="tofu", category="protein")
    recipe = Recipe(
        id=uuid.uuid4(),
        name="Test Tofu Bowl",
        description="A deterministic test recipe.",
        cuisine="Japanese",
        meal_type="dinner",
        calories=500,
        protein_g=Decimal("25"),
        carbs_g=Decimal("60"),
        fat_g=Decimal("15"),
        preparation_minutes=20,
        estimated_cost=Decimal("5"),
    )
    recipe.ingredients = [
        RecipeIngredient(ingredient=rice),
        RecipeIngredient(ingredient=tofu),
    ]
    return recipe, rice, tofu


def make_bare_recipe(name: str) -> Recipe:
    return Recipe(
        name=name,
        description=None,
        cuisine="American",
        meal_type="lunch",
        calories=500,
        protein_g=Decimal("20"),
        carbs_g=Decimal("60"),
        fat_g=Decimal("15"),
        preparation_minutes=15,
        estimated_cost=Decimal("5"),
    )


def test_scoring_components_sum_to_total() -> None:
    recipe, rice, tofu = make_recipe()
    context = ScoringContext(
        calorie_budget=500,
        meal_type="dinner",
        preferred_cuisines=frozenset({"japanese"}),
        pantry_statuses={rice.id: PantryStatus.AVAILABLE, tofu.id: PantryStatus.LOW},
        recent_food_names=frozenset(),
    )

    scored = score_recipe(recipe, context)

    assert scored.recommendation.score_breakdown.model_dump() == {
        "calorie_fit": 40.0,
        "pantry_coverage": 18.75,
        "cuisine_preference": 20.0,
        "meal_type_fit": 10.0,
        "variety": 5.0,
    }
    assert scored.recommendation.score == 93.75
    assert scored.recommendation.pantry_matches == ["rice", "tofu"]
    assert scored.recommendation.missing_ingredients == []


def test_recent_recipe_loses_variety_bonus() -> None:
    recipe, _, _ = make_recipe()
    base_context = ScoringContext(
        calorie_budget=500,
        meal_type=None,
        preferred_cuisines=frozenset(),
        pantry_statuses={},
        recent_food_names=frozenset(),
    )
    recent_context = ScoringContext(
        calorie_budget=500,
        meal_type=None,
        preferred_cuisines=frozenset(),
        pantry_statuses={},
        recent_food_names=frozenset({recipe.name.casefold()}),
    )

    fresh = score_recipe(recipe, base_context)
    recent = score_recipe(recipe, recent_context)

    assert fresh.recommendation.score - recent.recommendation.score == 5
    assert recent.recommendation.score_breakdown.variety == 0


def test_missing_optional_ingredient_does_not_reduce_pantry_coverage() -> None:
    recipe, rice, tofu = make_recipe()
    garnish = Ingredient(id=uuid.uuid4(), name="garnish", category="produce")
    recipe.ingredients.append(RecipeIngredient(ingredient=garnish, is_optional=True))
    context = ScoringContext(
        calorie_budget=500,
        meal_type=None,
        preferred_cuisines=frozenset(),
        pantry_statuses={rice.id: PantryStatus.AVAILABLE, tofu.id: PantryStatus.AVAILABLE},
        recent_food_names=frozenset(),
    )

    scored = score_recipe(recipe, context)

    assert scored.recommendation.score_breakdown.pantry_coverage == 25
    assert scored.recommendation.missing_ingredients == []
    assert scored.recommendation.explanations[1] == (
        "No cuisine preferences are currently selected"
    )


def test_equal_scores_and_calorie_distance_tie_break_by_name() -> None:
    user = make_user()
    make_profile(user, daily_calorie_target=1000)

    with make_sqlite_session() as session:
        session.add_all([user, make_bare_recipe("Zulu Bowl"), make_bare_recipe("Alpha Bowl")])
        session.commit()

        response = RecommendationService(session).next(
            user, limit=2, now=datetime(2026, 1, 15, 12, tzinfo=UTC)
        )

        assert [item.name for item in response.recommendations] == ["Alpha Bowl", "Zulu Bowl"]


def test_service_uses_next_slot_preferences_pantry_and_history() -> None:
    now = datetime(2026, 1, 15, 17, tzinfo=UTC)
    user = make_user()
    make_profile(user, daily_calorie_target=1200)
    dinner = make_schedule(user, "dinner")
    dinner.preferred_time = time(19)
    make_cuisine_preference(user, "Indian")

    with make_sqlite_session() as session:
        session.add(user)
        seed_database(session)
        session.flush()
        chickpea = session.scalar(select(Ingredient).where(Ingredient.name == "chickpeas"))
        rice = session.scalar(select(Ingredient).where(Ingredient.name == "rice"))
        assert chickpea is not None and rice is not None
        session.add_all(
            [
                PantryItem(
                    user=user, ingredient=chickpea, status=PantryStatus.AVAILABLE
                ),
                PantryItem(user=user, ingredient=rice, status=PantryStatus.AVAILABLE),
                MealLog(
                    user=user,
                    meal_type="lunch",
                    food_name="Paneer Spinach Skillet",
                    calories=400,
                    occurred_at=datetime(2026, 1, 15, 13, tzinfo=UTC),
                ),
            ]
        )
        session.commit()

        response = RecommendationService(session).next(user, limit=3, now=now)

        assert response.meal_type == "dinner"
        assert response.calorie_budget == 800
        assert len(response.recommendations) == 3
        assert response.recommendations[0].score >= response.recommendations[1].score
        assert any(
            item.score_breakdown.cuisine_preference == 20
            for item in response.recommendations
        )
        assert all(item.explanations for item in response.recommendations)


def test_recommendation_api_is_deterministic_and_honors_limit(
    recommendation_client: tuple[TestClient, Session],
) -> None:
    client, _ = recommendation_client
    auth = register(client)
    auth_headers = headers(auth["access_token"])
    onboard(client, auth_headers)
    client.put(
        "/preferences/cuisines",
        headers=auth_headers,
        json={"cuisines": ["Indian"]},
    )

    first = client.get("/recommendations/next?limit=3", headers=auth_headers)
    second = client.get("/recommendations/next?limit=3", headers=auth_headers)

    assert first.status_code == second.status_code == 200
    assert first.json() == second.json()
    assert len(first.json()["recommendations"]) == 3
    recommendations = first.json()["recommendations"]
    assert recommendations[0]["score"] >= recommendations[1]["score"]
    for recommendation in recommendations:
        assert recommendation["score"] == round(
            sum(recommendation["score_breakdown"].values()), 2
        )


def test_recommendation_preferences_are_isolated_by_user(
    recommendation_client: tuple[TestClient, Session],
) -> None:
    client, _ = recommendation_client
    first = register(client, "first@example.com")
    second = register(client, "second@example.com")
    first_headers = headers(first["access_token"])
    second_headers = headers(second["access_token"])
    onboard(client, first_headers)
    onboard(client, second_headers)
    client.put(
        "/preferences/cuisines",
        headers=first_headers,
        json={"cuisines": ["Indian"]},
    )
    client.put(
        "/preferences/cuisines",
        headers=second_headers,
        json={"cuisines": ["Japanese"]},
    )

    first_result = client.get("/recommendations/next?limit=1", headers=first_headers)
    second_result = client.get("/recommendations/next?limit=1", headers=second_headers)

    assert first_result.json()["recommendations"][0]["cuisine"] == "Indian"
    assert second_result.json()["recommendations"][0]["cuisine"] == "Japanese"


def test_recommendations_require_completed_profile(
    recommendation_client: tuple[TestClient, Session],
) -> None:
    client, _ = recommendation_client
    auth = register(client)

    response = client.get(
        "/recommendations/next", headers=headers(auth["access_token"])
    )

    assert response.status_code == 409


def test_recommendations_require_authentication(
    recommendation_client: tuple[TestClient, Session],
) -> None:
    client, _ = recommendation_client

    response = client.get("/recommendations/next")

    assert response.status_code == 401


@pytest.mark.parametrize("limit", [0, 21])
def test_recommendation_limit_is_validated(
    recommendation_client: tuple[TestClient, Session], limit: int
) -> None:
    client, _ = recommendation_client
    auth = register(client)

    response = client.get(
        f"/recommendations/next?limit={limit}", headers=headers(auth["access_token"])
    )

    assert response.status_code == 422
