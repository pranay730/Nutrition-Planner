from fastapi import APIRouter

from app.api.dependencies import CurrentUser, DatabaseSession
from app.onboarding.schemas import ProfileResponse, ProfileUpdate
from app.onboarding.service import OnboardingService

router = APIRouter(prefix="/onboarding", tags=["onboarding"])


@router.put("/profile", response_model=ProfileResponse)
def update_profile(
    payload: ProfileUpdate, current_user: CurrentUser, db: DatabaseSession
) -> ProfileResponse:
    profile = OnboardingService(db).upsert_profile(current_user, payload)
    return ProfileResponse.model_validate(profile)
