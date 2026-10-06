from fastapi import APIRouter, HTTPException, status

from app.api.dependencies import CurrentUser, DatabaseSession
from app.meals.schemas import DailyPlanResponse
from app.meals.service import DailyStateService, ProfileRequiredError

router = APIRouter(tags=["daily plan"])


@router.get("/daily-plan", response_model=DailyPlanResponse)
def get_daily_plan(current_user: CurrentUser, db: DatabaseSession) -> DailyPlanResponse:
    try:
        return DailyStateService(db).daily_plan(current_user)
    except ProfileRequiredError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
