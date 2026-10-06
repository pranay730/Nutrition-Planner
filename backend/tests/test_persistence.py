import pytest
from sqlalchemy import func, select

from app.models import Ingredient, IngredientCuisineTag, Recipe, RecipeIngredient
from app.seed import seed_database
from app.seed_data import INGREDIENTS, RECIPES, RecipeSeed
from tests.helpers import make_sqlite_session


def test_metadata_contains_phase_two_tables() -> None:
    from app.core.database import Base

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


def test_seed_catalog_is_internally_consistent() -> None:
    ingredient_names = [item["name"] for item in INGREDIENTS]
    recipe_names = [recipe["name"] for recipe in RECIPES]
    known = set(ingredient_names)

    assert len(set(ingredient_names)) == len(ingredient_names)
    assert len(set(recipe_names)) == len(recipe_names)
    assert not {name for recipe in RECIPES for name in recipe["ingredients"] if name not in known}


def test_seed_database_is_idempotent() -> None:
    with make_sqlite_session() as session:
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
    with make_sqlite_session() as session:
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


def test_seed_updates_category_and_cuisine_tags_without_duplicating() -> None:
    updated_rice = {
        "name": "rice",
        "category": "updated-grains",
        "cuisines": ["Indian"],
    }
    remaining = [item for item in INGREDIENTS if item["name"] != "rice"]

    with make_sqlite_session() as session:
        seed_database(session)
        seed_database(session, ingredients=[updated_rice, *remaining], recipes=RECIPES)

        rice = session.scalar(select(Ingredient).where(Ingredient.name == "rice"))
        ingredient_count = session.scalar(select(func.count()).select_from(Ingredient))
        recipe_count = session.scalar(select(func.count()).select_from(Recipe))

        assert rice is not None
        assert rice.category == "updated-grains"
        assert {tag.cuisine for tag in rice.cuisine_tags} == {"Indian"}
        assert ingredient_count == len(INGREDIENTS)
        assert recipe_count == len(RECIPES)


def test_seed_rejects_unknown_recipe_ingredient() -> None:
    recipe: RecipeSeed = {
        "name": "Impossible Dish",
        "description": "Uses an ingredient that is not in the catalog.",
        "cuisine": "American",
        "meal_type": "lunch",
        "calories": 400,
        "protein_g": 10,
        "carbs_g": 40,
        "fat_g": 10,
        "preparation_minutes": 15,
        "estimated_cost": 5,
        "ingredients": ["not-a-real-ingredient"],
    }

    with make_sqlite_session() as session, pytest.raises(ValueError, match="Unknown ingredients"):
        seed_database(session, ingredients=INGREDIENTS[:3], recipes=[recipe])
