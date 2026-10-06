from fastapi import APIRouter, HTTPException, status

from app.api.dependencies import CurrentUser, DatabaseSession
from app.meals.schemas import DailyMealsResponse, MealCreate, MealResponse
from app.meals.service import DailyStateService, FutureMealError, ProfileRequiredError

router = APIRouter(tags=["meals"])


@router.post("/meals", response_model=MealResponse, status_code=status.HTTP_201_CREATED)
def create_meal(
    payload: MealCreate, current_user: CurrentUser, db: DatabaseSession
) -> MealResponse:
    try:
        meal = DailyStateService(db).create_meal(current_user, payload)
    except FutureMealError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)
        ) from exc
    return MealResponse.model_validate(meal)


@router.get("/meals/today", response_model=DailyMealsResponse)
def get_meals_today(current_user: CurrentUser, db: DatabaseSession) -> DailyMealsResponse:
    try:
        local_date, timezone, meals = DailyStateService(db).meals_today(current_user)
    except ProfileRequiredError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    return DailyMealsResponse(
        date=local_date,
        timezone=timezone,
        total_calories=sum(meal.calories for meal in meals),
        meals=[MealResponse.model_validate(meal) for meal in meals],
    )
