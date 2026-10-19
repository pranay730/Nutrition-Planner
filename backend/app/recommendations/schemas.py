import uuid
from decimal import Decimal

from pydantic import BaseModel, Field


class ScoreBreakdown(BaseModel):
    calorie_fit: float = Field(ge=0, le=40)
    pantry_coverage: float = Field(ge=0, le=25)
    cuisine_preference: float = Field(ge=0, le=20)
    meal_type_fit: float = Field(ge=0, le=10)
    variety: float = Field(ge=0, le=5)


class RecipeRecommendation(BaseModel):
    recipe_id: uuid.UUID
    name: str
    description: str | None
    cuisine: str
    meal_type: str
    calories: int
    protein_g: Decimal
    carbs_g: Decimal
    fat_g: Decimal
    preparation_minutes: int
    estimated_cost: Decimal
    score: float = Field(ge=0, le=100)
    score_breakdown: ScoreBreakdown
    pantry_matches: list[str]
    missing_ingredients: list[str]
    explanations: list[str]


class NextRecommendationResponse(BaseModel):
    meal_type: str | None
    calorie_budget: int
    recommendations: list[RecipeRecommendation]
