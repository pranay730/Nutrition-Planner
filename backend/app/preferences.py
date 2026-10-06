from fastapi import APIRouter, HTTPException, status

from app.api.dependencies import CurrentUser, DatabaseSession
from app.onboarding.schemas import CuisinePreferencesResponse, CuisinePreferencesUpdate
from app.onboarding.service import OnboardingService

router = APIRouter(prefix="/preferences", tags=["preferences"])


@router.put("/cuisines", response_model=CuisinePreferencesResponse)
def update_cuisines(
    payload: CuisinePreferencesUpdate, current_user: CurrentUser, db: DatabaseSession
) -> CuisinePreferencesResponse:
    try:
        cuisines = OnboardingService(db).replace_cuisines(current_user, payload.cuisines)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)
        ) from exc
    return CuisinePreferencesResponse(cuisines=cuisines)
