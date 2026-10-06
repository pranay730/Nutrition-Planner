from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.models import CuisinePreference, IngredientCuisineTag, MealSchedule, Profile, User
from app.models.enums import ActivityLevel, CalculationSex, GoalType
from app.onboarding.schemas import MealScheduleInput, ProfileUpdate

ACTIVITY_FACTORS = {
    ActivityLevel.SEDENTARY: Decimal("1.2"),
    ActivityLevel.LIGHT: Decimal("1.375"),
    ActivityLevel.MODERATE: Decimal("1.55"),
    ActivityLevel.ACTIVE: Decimal("1.725"),
    ActivityLevel.VERY_ACTIVE: Decimal("1.9"),
}
GOAL_ADJUSTMENTS = {
    GoalType.LOSE: Decimal("-500"),
    GoalType.MAINTAIN: Decimal("0"),
    GoalType.GAIN: Decimal("500"),
}


def calculate_daily_calorie_target(data: ProfileUpdate) -> int:
    sex_adjustment = (
        Decimal("5") if data.calculation_sex == CalculationSex.MALE else Decimal("-161")
    )
    basal_metabolic_rate = (
        Decimal("10") * data.weight_kg
        + Decimal("6.25") * data.height_cm
        - Decimal("5") * data.age
        + sex_adjustment
    )
    target = basal_metabolic_rate * ACTIVITY_FACTORS[data.activity_level]
    target += GOAL_ADJUSTMENTS[data.goal_type]
    minimum = Decimal("1500") if data.calculation_sex == CalculationSex.MALE else Decimal("1200")
    bounded_target = min(max(target, minimum), Decimal("10000"))
    return int(bounded_target.quantize(Decimal("1"), rounding=ROUND_HALF_UP))


class OnboardingService:
    def __init__(self, session: Session) -> None:
        self.session = session

    def upsert_profile(self, user: User, data: ProfileUpdate) -> Profile:
        profile = user.profile or Profile(user=user)
        for field, value in data.model_dump().items():
            setattr(profile, field, value)
        profile.daily_calorie_target = calculate_daily_calorie_target(data)
        self.session.add(profile)
        self.session.commit()
        self.session.refresh(profile)
        return profile

    def replace_cuisines(self, user: User, cuisines: list[str]) -> list[str]:
        canonical = self._canonical_cuisines(cuisines)
        self.session.execute(
            delete(CuisinePreference).where(CuisinePreference.user_id == user.id)
        )
        self.session.add_all(
            [CuisinePreference(user_id=user.id, cuisine=cuisine) for cuisine in canonical]
        )
        self.session.commit()
        return canonical

    def replace_schedules(
        self, user: User, schedules: list[MealScheduleInput]
    ) -> list[MealSchedule]:
        existing = {schedule.meal_type: schedule for schedule in user.meal_schedules}
        requested_types = {item.meal_type for item in schedules}
        for meal_type in existing.keys() - requested_types:
            self.session.delete(existing[meal_type])
        result = []
        for item in schedules:
            schedule = existing.get(item.meal_type) or MealSchedule(
                user_id=user.id, meal_type=item.meal_type
            )
            for field, value in item.model_dump().items():
                setattr(schedule, field, value)
            self.session.add(schedule)
            result.append(schedule)
        self.session.commit()
        for schedule in result:
            self.session.refresh(schedule)
        return sorted(result, key=lambda schedule: (schedule.preferred_time, schedule.meal_type))

    def _canonical_cuisines(self, cuisines: list[str]) -> list[str]:
        known = self.session.scalars(select(IngredientCuisineTag.cuisine).distinct()).all()
        canonical_by_name = {value.casefold(): value for value in known}
        unknown = [value for value in cuisines if value.casefold() not in canonical_by_name]
        if unknown:
            raise ValueError(f"Unknown cuisines: {', '.join(unknown)}")
        return [canonical_by_name[value.casefold()] for value in cuisines]
