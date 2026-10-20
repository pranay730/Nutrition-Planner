import uuid
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import delete, func, select

from app.api.dependencies import CurrentUser, DatabaseSession
from app.models import CuisinePreference, Ingredient, IngredientCuisineTag, PantryItem
from app.models.enums import PantryStatus

router = APIRouter(tags=["pantry"])


class IngredientSuggestion(BaseModel):
    id: uuid.UUID
    name: str
    category: str
    matching_cuisines: list[str]


class PantryItemInput(BaseModel):
    ingredient_id: uuid.UUID
    status: PantryStatus = PantryStatus.AVAILABLE


class PantryReplace(BaseModel):
    items: list[PantryItemInput] = Field(max_length=200)


class PantryStatusUpdate(BaseModel):
    status: PantryStatus


class PantryItemResponse(BaseModel):
    id: uuid.UUID
    ingredient_id: uuid.UUID
    name: str
    category: str
    status: PantryStatus


def _response(item: PantryItem) -> PantryItemResponse:
    return PantryItemResponse(
        id=item.id,
        ingredient_id=item.ingredient_id,
        name=item.ingredient.name,
        category=item.ingredient.category,
        status=item.status,
    )


@router.get("/ingredients/suggestions", response_model=list[IngredientSuggestion])
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
                id=item.id, name=item.name, category=item.category, matching_cuisines=[]
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
            id=ingredient.id,
            name=ingredient.name,
            category=ingredient.category,
            matching_cuisines=sorted(
                tag.cuisine for tag in ingredient.cuisine_tags if tag.cuisine in preferred
            ),
        )
        for ingredient, _count in rows
    ]


@router.get("/pantry", response_model=list[PantryItemResponse])
def get_pantry(current_user: CurrentUser, db: DatabaseSession) -> list[PantryItemResponse]:
    items = db.scalars(
        select(PantryItem)
        .join(PantryItem.ingredient)
        .where(PantryItem.user_id == current_user.id)
        .order_by(Ingredient.category, Ingredient.name)
    ).all()
    return [_response(item) for item in items]


@router.put("/pantry", response_model=list[PantryItemResponse])
def replace_pantry(
    payload: PantryReplace, current_user: CurrentUser, db: DatabaseSession
) -> list[PantryItemResponse]:
    ingredient_ids = [item.ingredient_id for item in payload.items]
    if len(set(ingredient_ids)) != len(ingredient_ids):
        raise HTTPException(status_code=422, detail="Pantry ingredients must be unique")
    known = set(db.scalars(select(Ingredient.id).where(Ingredient.id.in_(ingredient_ids))).all())
    if known != set(ingredient_ids):
        raise HTTPException(status_code=422, detail="Unknown ingredient")
    db.execute(delete(PantryItem).where(PantryItem.user_id == current_user.id))
    items = [
        PantryItem(user_id=current_user.id, ingredient_id=item.ingredient_id, status=item.status)
        for item in payload.items
    ]
    db.add_all(items)
    db.commit()
    for item in items:
        db.refresh(item)
    return [_response(item) for item in items]


@router.put("/pantry/{ingredient_id}", response_model=PantryItemResponse)
def update_pantry_item(
    ingredient_id: uuid.UUID,
    payload: PantryStatusUpdate,
    current_user: CurrentUser,
    db: DatabaseSession,
) -> PantryItemResponse:
    ingredient = db.get(Ingredient, ingredient_id)
    if ingredient is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ingredient not found")
    item = db.scalar(
        select(PantryItem).where(
            PantryItem.user_id == current_user.id, PantryItem.ingredient_id == ingredient_id
        )
    )
    if item is None:
        item = PantryItem(user_id=current_user.id, ingredient=ingredient)
    item.status = payload.status
    db.add(item)
    db.commit()
    db.refresh(item)
    return _response(item)
