from datetime import UTC, date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy.orm import Session

from app.meals.repository import MealRepository
from app.meals.schemas import DailyPlanResponse, MealAllocation, MealCreate
from app.models import MealLog, Profile, User


class ProfileRequiredError(ValueError):
    pass


class FutureMealError(ValueError):
    pass


def utc_now() -> datetime:
    return datetime.now(UTC)


def local_day_bounds(now: datetime, timezone: str) -> tuple[date, datetime, datetime]:
    zone = ZoneInfo(timezone)
    local_date = now.astimezone(zone).date()
    start = datetime.combine(local_date, time.min, tzinfo=zone).astimezone(UTC)
    end = datetime.combine(local_date + timedelta(days=1), time.min, tzinfo=zone).astimezone(UTC)
    return local_date, start, end


def allocate_calories(
    remaining_calories: int, meal_slots: list[tuple[str, time]]
) -> list[MealAllocation]:
    if not meal_slots:
        return []
    quotient, remainder = divmod(max(remaining_calories, 0), len(meal_slots))
    return [
        MealAllocation(
            meal_type=meal_type,
            scheduled_time=scheduled_time,
            allocated_calories=quotient + (1 if index < remainder else 0),
        )
        for index, (meal_type, scheduled_time) in enumerate(meal_slots)
    ]


class DailyStateService:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.meals = MealRepository(session)

    def create_meal(
        self, user: User, data: MealCreate, *, now: datetime | None = None
    ) -> MealLog:
        current_time = now or utc_now()
        occurred_at = (data.occurred_at or current_time).astimezone(UTC)
        if occurred_at > current_time + timedelta(minutes=5):
            raise FutureMealError("occurred_at cannot be in the future")
        meal = MealLog(
            user_id=user.id,
            meal_type=data.meal_type,
            food_name=data.food_name,
            calories=data.calories,
            occurred_at=occurred_at,
            notes=data.notes,
        )
        self.meals.add(meal)
        self.session.commit()
        self.session.refresh(meal)
        return meal

    def meals_today(
        self, user: User, *, now: datetime | None = None
    ) -> tuple[date, str, list[MealLog]]:
        profile = self._require_profile(user)
        local_date, start, end = local_day_bounds(now or utc_now(), profile.timezone)
        return local_date, profile.timezone, self.meals.list_between(user.id, start, end)

    def daily_plan(self, user: User, *, now: datetime | None = None) -> DailyPlanResponse:
        current_time = now or utc_now()
        profile = self._require_profile(user)
        local_date, start, end = local_day_bounds(current_time, profile.timezone)
        meals = self.meals.list_between(user.id, start, end)
        consumed = sum(meal.calories for meal in meals)
        remaining = profile.daily_calorie_target - consumed
        local_time = current_time.astimezone(ZoneInfo(profile.timezone)).time().replace(tzinfo=None)
        logged_types = {meal.meal_type for meal in meals}
        meal_slots = sorted(
            (
                (schedule.meal_type, schedule.preferred_time)
                for schedule in user.meal_schedules
                if schedule.preferred_time >= local_time
                and schedule.meal_type not in logged_types
            ),
            key=lambda item: (item[1], item[0]),
        )
        return DailyPlanResponse(
            date=local_date,
            timezone=profile.timezone,
            calorie_target=profile.daily_calorie_target,
            consumed_calories=consumed,
            remaining_calories=remaining,
            allocations=allocate_calories(remaining, meal_slots),
        )

    @staticmethod
    def _require_profile(user: User) -> Profile:
        if user.profile is None:
            raise ProfileRequiredError("Complete onboarding before using daily state")
        return user.profile
