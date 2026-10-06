import uuid
from datetime import UTC, date, datetime, time

from pydantic import BaseModel, ConfigDict, Field, field_validator


class MealCreate(BaseModel):
    meal_type: str = Field(min_length=1, max_length=32)
    food_name: str | None = Field(default=None, max_length=160)
    calories: int = Field(gt=0, le=10000)
    occurred_at: datetime | None = None
    notes: str | None = Field(default=None, max_length=2000)

    @field_validator("meal_type")
    @classmethod
    def normalize_meal_type(cls, value: str) -> str:
        normalized = value.strip().casefold()
        if not normalized:
            raise ValueError("Meal type cannot be blank")
        return normalized

    @field_validator("food_name", "notes")
    @classmethod
    def normalize_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None

    @field_validator("occurred_at")
    @classmethod
    def timestamp_must_include_timezone(cls, value: datetime | None) -> datetime | None:
        if value is not None and (value.tzinfo is None or value.utcoffset() is None):
            raise ValueError("occurred_at must include a timezone offset")
        return value


class MealResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    meal_type: str
    food_name: str | None
    calories: int
    occurred_at: datetime
    notes: str | None
    created_at: datetime

    @field_validator("occurred_at", "created_at", mode="before")
    @classmethod
    def serialize_database_timestamp_as_utc(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value.astimezone(UTC)


class DailyMealsResponse(BaseModel):
    date: date
    timezone: str
    total_calories: int
    meals: list[MealResponse]


class MealAllocation(BaseModel):
    meal_type: str
    scheduled_time: time
    allocated_calories: int


class DailyPlanResponse(BaseModel):
    date: date
    timezone: str
    calorie_target: int
    consumed_calories: int
    remaining_calories: int
    allocations: list[MealAllocation]
