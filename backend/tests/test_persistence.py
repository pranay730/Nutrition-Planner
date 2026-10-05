from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.core.database import Base
from app.models import Ingredient, IngredientCuisineTag, Recipe, RecipeIngredient
from app.seed import seed_database
from app.seed_data import INGREDIENTS, RECIPES


def make_session() -> Session:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    return Session(engine)


def test_metadata_contains_phase_two_tables() -> None:
    assert set(Base.metadata.tables) == {
        "cuisine_preferences",
        "ingredient_cuisine_tags",
        "ingredients",
        "meal_logs",
        "meal_schedules",
        "notifications",
        "pantry_items",
        "profiles",
        "recipe_ingredients",
        "recipes",
        "users",
    }


def test_seed_database_is_idempotent() -> None:
    with make_session() as session:
        first_result = seed_database(session)
        second_result = seed_database(session)

        ingredient_count = session.scalar(select(func.count()).select_from(Ingredient))
        recipe_count = session.scalar(select(func.count()).select_from(Recipe))
        tag_count = session.scalar(select(func.count()).select_from(IngredientCuisineTag))
        recipe_ingredient_count = session.scalar(select(func.count()).select_from(RecipeIngredient))

    assert first_result == second_result == (len(INGREDIENTS), len(RECIPES))
    assert ingredient_count == len(INGREDIENTS)
    assert recipe_count == len(RECIPES)
    assert tag_count and tag_count > len(INGREDIENTS)
    assert recipe_ingredient_count == sum(len(recipe["ingredients"]) for recipe in RECIPES)


def test_seeded_recipes_reference_canonical_ingredients() -> None:
    with make_session() as session:
        seed_database(session)
        bowl = session.scalar(select(Recipe).where(Recipe.name == "Chickpea Rice Bowl"))

        assert bowl is not None
        assert {item.ingredient.name for item in bowl.ingredients} == {
            "chickpeas",
            "onion",
            "rice",
            "tomato",
            "yogurt",
        }
