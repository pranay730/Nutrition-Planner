from datetime import date, datetime, time
from decimal import Decimal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.models.enums import ActivityLevel, CalculationSex, GoalType


class ProfileUpdate(BaseModel):
    age: int = Field(ge=13, le=120)
    calculation_sex: CalculationSex
    height_cm: Decimal = Field(ge=80, le=250, max_digits=5, decimal_places=2)
    weight_kg: Decimal = Field(ge=25, le=500, max_digits=6, decimal_places=2)
    activity_level: ActivityLevel
    goal_type: GoalType
    goal_weight_kg: Decimal | None = Field(
        default=None, ge=25, le=500, max_digits=6, decimal_places=2
    )
    target_date: date | None = None
    timezone: str = Field(default="UTC", min_length=1, max_length=64)

    @field_validator("timezone")
    @classmethod
    def timezone_must_be_iana_name(cls, value: str) -> str:
        try:
            ZoneInfo(value)
        except ZoneInfoNotFoundError as exc:
            raise ValueError("Timezone must be a valid IANA timezone") from exc
        return value

    @model_validator(mode="after")
    def validate_goal(self) -> "ProfileUpdate":
        if self.goal_type == GoalType.MAINTAIN:
            return self
        if self.goal_weight_kg is None or self.target_date is None:
            raise ValueError("Weight-change goals require goal_weight_kg and target_date")
        if self.target_date <= date.today():
            raise ValueError("target_date must be in the future")
        if self.goal_type == GoalType.LOSE and self.goal_weight_kg >= self.weight_kg:
            raise ValueError("A weight-loss goal must be below current weight")
        if self.goal_type == GoalType.GAIN and self.goal_weight_kg <= self.weight_kg:
            raise ValueError("A weight-gain goal must be above current weight")
        return self


class ProfileResponse(ProfileUpdate):
    model_config = ConfigDict(from_attributes=True)

    daily_calorie_target: int
    created_at: datetime
    updated_at: datetime


class CuisinePreferencesUpdate(BaseModel):
    cuisines: list[str] = Field(max_length=20)

    @field_validator("cuisines")
    @classmethod
    def normalize_cuisines(cls, values: list[str]) -> list[str]:
        normalized = [value.strip() for value in values]
        if any(not value or len(value) > 64 for value in normalized):
            raise ValueError("Cuisine names must contain 1 to 64 characters")
        deduplicated = list(dict.fromkeys(value.casefold() for value in normalized))
        if len(deduplicated) != len(normalized):
            raise ValueError("Cuisine preferences must be unique")
        return normalized


class CuisinePreferencesResponse(BaseModel):
    cuisines: list[str]


class MealScheduleInput(BaseModel):
    meal_type: str = Field(min_length=1, max_length=32)
    preferred_time: time
    reminder_minutes_before: int = Field(default=15, ge=0, le=180)
    reminder_enabled: bool = True

    @field_validator("meal_type")
    @classmethod
    def normalize_meal_type(cls, value: str) -> str:
        normalized = value.strip().casefold()
        if not normalized:
            raise ValueError("Meal type cannot be blank")
        return normalized


class MealSchedulesUpdate(BaseModel):
    schedules: list[MealScheduleInput] = Field(max_length=12)

    @field_validator("schedules")
    @classmethod
    def meal_types_must_be_unique(
        cls, values: list[MealScheduleInput]
    ) -> list[MealScheduleInput]:
        meal_types = [value.meal_type for value in values]
        if len(set(meal_types)) != len(meal_types):
            raise ValueError("Meal types must be unique")
        return values


class MealScheduleResponse(MealScheduleInput):
    model_config = ConfigDict(from_attributes=True)


class MealSchedulesResponse(BaseModel):
    schedules: list[MealScheduleResponse]
