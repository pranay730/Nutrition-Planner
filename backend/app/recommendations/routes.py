from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, status

from app.api.dependencies import CurrentUser, DatabaseSession
from app.meals.service import ProfileRequiredError
from app.recommendations.schemas import NextRecommendationResponse
from app.recommendations.service import RecommendationService

router = APIRouter(prefix="/recommendations", tags=["recommendations"])


@router.get("/next", response_model=NextRecommendationResponse)
def get_next_recommendations(
    current_user: CurrentUser,
    db: DatabaseSession,
    limit: Annotated[int, Query(ge=1, le=20)] = 5,
) -> NextRecommendationResponse:
    try:
        return RecommendationService(db).next(current_user, limit=limit)
    except ProfileRequiredError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
