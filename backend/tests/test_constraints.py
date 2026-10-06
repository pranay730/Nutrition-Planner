from datetime import time

import pytest
from sqlalchemy import delete
from sqlalchemy.exc import IntegrityError

from app.models import Ingredient, PantryItem, Recipe, RecipeIngredient, User
from app.models.schedule import MealSchedule
from tests.helpers import (
    make_cuisine_preference,
    make_pantry_item,
    make_profile,
    make_schedule,
    make_sqlite_session,
    make_user,
)


def test_user_email_is_unique() -> None:
    with make_sqlite_session() as session:
        session.add(make_user())
        session.commit()
        session.add(make_user())
        with pytest.raises(IntegrityError):
            session.commit()


def test_cuisine_preference_is_unique_per_user() -> None:
    user = make_user()
    make_cuisine_preference(user, "Indian")
    make_cuisine_preference(user, "Indian")

    with make_sqlite_session() as session:
        session.add(user)
        with pytest.raises(IntegrityError):
            session.commit()


def test_meal_schedule_is_unique_per_user_and_meal_type() -> None:
    user = make_user()
    make_schedule(user, "lunch")
    user.meal_schedules.append(
        MealSchedule(meal_type="lunch", preferred_time=time(13, 0), reminder_minutes_before=10)
    )

    with make_sqlite_session() as session:
        session.add(user)
        with pytest.raises(IntegrityError):
            session.commit()


def test_pantry_item_is_unique_per_user_and_ingredient() -> None:
    user = make_user()
    ingredient = Ingredient(name="rice", category="grains")
    make_pantry_item(user, ingredient)
    make_pantry_item(user, ingredient)

    with make_sqlite_session() as session:
        session.add_all([user, ingredient])
        with pytest.raises(IntegrityError):
            session.commit()


def test_profile_rejects_out_of_range_age() -> None:
    user = make_user()
    make_profile(user, age=5)

    with make_sqlite_session() as session:
        session.add(user)
        with pytest.raises(IntegrityError):
            session.commit()


def test_recipe_rejects_nonpositive_calories() -> None:
    recipe = Recipe(
        name="Empty Plate",
        cuisine="American",
        meal_type="lunch",
        calories=0,
        protein_g=0,
        carbs_g=0,
        fat_g=0,
        preparation_minutes=10,
        estimated_cost=0,
    )

    with make_sqlite_session() as session:
        session.add(recipe)
        with pytest.raises(IntegrityError):
            session.commit()


def test_schedule_rejects_out_of_range_reminder_lead_time() -> None:
    user = make_user()
    user.meal_schedules.append(
        MealSchedule(meal_type="dinner", preferred_time=time(18, 0), reminder_minutes_before=240)
    )

    with make_sqlite_session() as session:
        session.add(user)
        with pytest.raises(IntegrityError):
            session.commit()


def test_deleting_user_cascades_owned_rows() -> None:
    user = make_user()
    ingredient = Ingredient(name="rice", category="grains")
    pantry_item = make_pantry_item(user, ingredient)
    make_cuisine_preference(user)
    make_schedule(user)
    make_profile(user)

    with make_sqlite_session() as session:
        session.add_all([user, ingredient])
        session.commit()
        user_id = user.id
        pantry_id = pantry_item.id
        ingredient_id = ingredient.id

        session.execute(delete(User).where(User.id == user_id))
        session.commit()

        assert session.get(User, user_id) is None
        assert session.get(PantryItem, pantry_id) is None
        assert session.get(Ingredient, ingredient_id) is not None


def test_deleting_used_ingredient_is_restricted() -> None:
    ingredient = Ingredient(name="rice", category="grains")
    recipe = Recipe(
        name="Rice Bowl",
        cuisine="Indian",
        meal_type="lunch",
        calories=400,
        protein_g=8,
        carbs_g=70,
        fat_g=6,
        preparation_minutes=20,
        estimated_cost=4,
    )
    recipe.ingredients.append(RecipeIngredient(ingredient=ingredient))

    with make_sqlite_session() as session:
        session.add(recipe)
        session.commit()

        with pytest.raises(IntegrityError):
            session.execute(delete(Ingredient).where(Ingredient.id == ingredient.id))
            session.commit()
