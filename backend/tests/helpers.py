from datetime import time
from decimal import Decimal

from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app import models as _models  # noqa: F401
from app.core.database import Base
from app.models import Ingredient, PantryItem, User
from app.models.enums import ActivityLevel, CalculationSex, GoalType, PantryStatus
from app.models.profile import CuisinePreference, Profile
from app.models.schedule import MealSchedule


def make_sqlite_session() -> Session:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    @event.listens_for(engine, "connect")
    def _enable_foreign_keys(dbapi_connection, _connection_record) -> None:
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    Base.metadata.create_all(engine)
    return Session(engine)


def make_user(email: str = "pat@example.com") -> User:
    return User(email=email, password_hash="not-a-real-hash")


def make_profile(user: User, *, age: int = 30, daily_calorie_target: int = 2000) -> Profile:
    return Profile(
        user=user,
        age=age,
        calculation_sex=CalculationSex.FEMALE,
        height_cm=Decimal("170.00"),
        weight_kg=Decimal("70.00"),
        activity_level=ActivityLevel.MODERATE,
        goal_type=GoalType.MAINTAIN,
        daily_calorie_target=daily_calorie_target,
    )


def make_pantry_item(user: User, ingredient: Ingredient) -> PantryItem:
    item = PantryItem(user=user, ingredient=ingredient, status=PantryStatus.AVAILABLE)
    user.pantry_items.append(item)
    return item


def make_schedule(user: User, meal_type: str = "lunch") -> MealSchedule:
    schedule = MealSchedule(
        user=user, meal_type=meal_type, preferred_time=time(12, 0), reminder_minutes_before=15
    )
    user.meal_schedules.append(schedule)
    return schedule


def make_cuisine_preference(user: User, cuisine: str = "Indian") -> CuisinePreference:
    preference = CuisinePreference(user=user, cuisine=cuisine)
    user.cuisine_preferences.append(preference)
    return preference
