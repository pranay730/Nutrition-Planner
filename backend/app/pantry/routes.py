from typing import Annotated

from fastapi import APIRouter, Query
from pydantic import BaseModel, ConfigDict
from sqlalchemy import func, select

from app.api.dependencies import CurrentUser, DatabaseSession
from app.models import CuisinePreference, Ingredient, IngredientCuisineTag

router = APIRouter(prefix="/ingredients", tags=["ingredients"])


class IngredientSuggestion(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    category: str
    matching_cuisines: list[str]


@router.get("/suggestions", response_model=list[IngredientSuggestion])
def get_ingredient_suggestions(
    current_user: CurrentUser,
    db: DatabaseSession,
    limit: Annotated[int, Query(ge=1, le=100)] = 30,
) -> list[IngredientSuggestion]:
    preferred = db.scalars(
        select(CuisinePreference.cuisine).where(CuisinePreference.user_id == current_user.id)
    ).all()
    if not preferred:
        ingredients = db.scalars(select(Ingredient).order_by(Ingredient.name).limit(limit)).all()
        return [
            IngredientSuggestion(
                id=str(item.id), name=item.name, category=item.category, matching_cuisines=[]
            )
            for item in ingredients
        ]

    rows = db.execute(
        select(Ingredient, func.count(IngredientCuisineTag.id).label("match_count"))
        .join(Ingredient.cuisine_tags)
        .where(IngredientCuisineTag.cuisine.in_(preferred))
        .group_by(Ingredient.id)
        .order_by(func.count(IngredientCuisineTag.id).desc(), Ingredient.name)
        .limit(limit)
    ).all()
    return [
        IngredientSuggestion(
            id=str(ingredient.id),
            name=ingredient.name,
            category=ingredient.category,
            matching_cuisines=sorted(
                tag.cuisine for tag in ingredient.cuisine_tags if tag.cuisine in preferred
            ),
        )
        for ingredient, _match_count in rows
    ]
