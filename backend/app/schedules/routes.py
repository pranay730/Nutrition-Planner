from fastapi import APIRouter

from app.api.dependencies import CurrentUser, DatabaseSession
from app.onboarding.schemas import MealSchedulesResponse, MealSchedulesUpdate
from app.onboarding.service import OnboardingService

router = APIRouter(prefix="/meal-schedules", tags=["meal schedules"])


@router.put("", response_model=MealSchedulesResponse)
def update_schedules(
    payload: MealSchedulesUpdate, current_user: CurrentUser, db: DatabaseSession
) -> MealSchedulesResponse:
    schedules = OnboardingService(db).replace_schedules(current_user, payload.schedules)
    return MealSchedulesResponse(schedules=schedules)
