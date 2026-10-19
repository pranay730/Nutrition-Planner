import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.meals.service import DailyStateService
from app.models import CuisinePreference, MealLog, PantryItem, Recipe, RecipeIngredient, User
from app.models.enums import PantryStatus
from app.recommendations.schemas import (
    NextRecommendationResponse,
    RecipeRecommendation,
    ScoreBreakdown,
)


@dataclass(frozen=True)
class ScoringContext:
    calorie_budget: int
    meal_type: str | None
    preferred_cuisines: frozenset[str]
    pantry_statuses: dict[uuid.UUID, PantryStatus]
    recent_food_names: frozenset[str]


@dataclass(frozen=True)
class ScoredRecipe:
    recommendation: RecipeRecommendation
    calorie_distance: int


def _rounded(value: float) -> float:
    return round(value + 1e-12, 2)


def score_recipe(recipe: Recipe, context: ScoringContext) -> ScoredRecipe:
    calorie_distance = abs(recipe.calories - context.calorie_budget)
    calorie_denominator = max(recipe.calories, context.calorie_budget, 1)
    calorie_score = 40 * max(0.0, 1 - calorie_distance / calorie_denominator)
    cuisine_score = 20.0 if recipe.cuisine.casefold() in context.preferred_cuisines else 0.0
    meal_type_score = (
        10.0 if context.meal_type is not None and recipe.meal_type == context.meal_type else 0.0
    )
    variety_score = 0.0 if recipe.name.casefold() in context.recent_food_names else 5.0

    pantry_points = 0.0
    pantry_matches: list[str] = []
    missing_ingredients: list[str] = []
    required_ingredients = [item for item in recipe.ingredients if not item.is_optional]
    for association in required_ingredients:
        ingredient = association.ingredient
        status = context.pantry_statuses.get(ingredient.id)
        if status == PantryStatus.AVAILABLE:
            pantry_points += 1
            pantry_matches.append(ingredient.name)
        elif status == PantryStatus.LOW:
            pantry_points += 0.5
            pantry_matches.append(ingredient.name)
        else:
            missing_ingredients.append(ingredient.name)
    ingredient_count = len(required_ingredients)
    pantry_score = 25 * pantry_points / ingredient_count if ingredient_count else 0.0

    breakdown = ScoreBreakdown(
        calorie_fit=_rounded(calorie_score),
        pantry_coverage=_rounded(pantry_score),
        cuisine_preference=cuisine_score,
        meal_type_fit=meal_type_score,
        variety=variety_score,
    )
    total = _rounded(sum(breakdown.model_dump().values()))
    explanations = [
        f"{recipe.calories} calories versus a {context.calorie_budget}-calorie budget",
        _cuisine_explanation(recipe.cuisine, context.preferred_cuisines, cuisine_score),
        f"{len(pantry_matches)} of {ingredient_count} ingredients are available or low",
        _meal_type_explanation(context.meal_type, meal_type_score),
        (
            "Adds variety versus meals logged in the last 7 days"
            if variety_score
            else "Recently logged, so no variety bonus"
        ),
    ]
    return ScoredRecipe(
        recommendation=RecipeRecommendation(
            recipe_id=recipe.id,
            name=recipe.name,
            description=recipe.description,
            cuisine=recipe.cuisine,
            meal_type=recipe.meal_type,
            calories=recipe.calories,
            protein_g=recipe.protein_g,
            carbs_g=recipe.carbs_g,
            fat_g=recipe.fat_g,
            preparation_minutes=recipe.preparation_minutes,
            estimated_cost=recipe.estimated_cost,
            score=total,
            score_breakdown=breakdown,
            pantry_matches=sorted(pantry_matches),
            missing_ingredients=sorted(missing_ingredients),
            explanations=explanations,
        ),
        calorie_distance=calorie_distance,
    )


def _cuisine_explanation(
    cuisine: str, preferred_cuisines: frozenset[str], score: float
) -> str:
    if not preferred_cuisines:
        return "No cuisine preferences are currently selected"
    if score:
        return f"{cuisine} matches a preferred cuisine"
    return f"{cuisine} is outside current cuisine preferences"


def _meal_type_explanation(meal_type: str | None, score: float) -> str:
    if meal_type is None:
        return "No upcoming meal slot is currently available"
    if score:
        return f"Matches the next {meal_type} slot"
    return f"Does not match the next {meal_type} slot"


class RecommendationService:
    def __init__(self, session: Session) -> None:
        self.session = session

    def next(
        self, user: User, *, limit: int = 5, now: datetime | None = None
    ) -> NextRecommendationResponse:
        current_time = now or datetime.now(UTC)
        plan = DailyStateService(self.session).daily_plan(user, now=current_time)
        next_allocation = plan.allocations[0] if plan.allocations else None
        calorie_budget = (
            next_allocation.allocated_calories
            if next_allocation is not None
            else max(plan.remaining_calories, 0)
        )
        meal_type = next_allocation.meal_type if next_allocation is not None else None
        preferred = self.session.scalars(
            select(CuisinePreference.cuisine).where(CuisinePreference.user_id == user.id)
        ).all()
        pantry_items = self.session.scalars(
            select(PantryItem).where(PantryItem.user_id == user.id)
        ).all()
        recent_names = self.session.scalars(
            select(MealLog.food_name).where(
                MealLog.user_id == user.id,
                MealLog.occurred_at >= current_time - timedelta(days=7),
                MealLog.occurred_at <= current_time,
                MealLog.food_name.is_not(None),
            )
        ).all()
        context = ScoringContext(
            calorie_budget=calorie_budget,
            meal_type=meal_type,
            preferred_cuisines=frozenset(value.casefold() for value in preferred),
            pantry_statuses={item.ingredient_id: item.status for item in pantry_items},
            recent_food_names=frozenset(value.casefold() for value in recent_names if value),
        )
        recipes = self.session.scalars(
            select(Recipe)
            .options(
                selectinload(Recipe.ingredients).selectinload(RecipeIngredient.ingredient)
            )
            .order_by(Recipe.name)
        ).all()
        scored = [score_recipe(recipe, context) for recipe in recipes]
        scored.sort(
            key=lambda item: (
                -item.recommendation.score,
                item.calorie_distance,
                item.recommendation.name,
            )
        )
        return NextRecommendationResponse(
            meal_type=meal_type,
            calorie_budget=calorie_budget,
            recommendations=[item.recommendation for item in scored[:limit]],
        )
