from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.models import Ingredient, IngredientCuisineTag, Recipe, RecipeIngredient
from app.seed_data import INGREDIENTS, RECIPES, IngredientSeed, RecipeSeed


def _seed_ingredient(session: Session, data: IngredientSeed) -> Ingredient:
    ingredient = session.scalar(select(Ingredient).where(Ingredient.name == data["name"]))
    if ingredient is None:
        ingredient = Ingredient(name=data["name"], category=data["category"])
        session.add(ingredient)
    else:
        ingredient.category = data["category"]

    tags_by_cuisine = {tag.cuisine: tag for tag in ingredient.cuisine_tags}
    expected_cuisines = set(data["cuisines"])
    for cuisine in expected_cuisines - tags_by_cuisine.keys():
        ingredient.cuisine_tags.append(IngredientCuisineTag(cuisine=cuisine))
    for cuisine in tags_by_cuisine.keys() - expected_cuisines:
        session.delete(tags_by_cuisine[cuisine])
    return ingredient


def _seed_recipe(
    session: Session, data: RecipeSeed, ingredients_by_name: dict[str, Ingredient]
) -> Recipe:
    recipe = session.scalar(select(Recipe).where(Recipe.name == data["name"]))
    if recipe is None:
        recipe = Recipe(name=data["name"])
        session.add(recipe)

    for field in (
        "description",
        "cuisine",
        "meal_type",
        "calories",
        "protein_g",
        "carbs_g",
        "fat_g",
        "preparation_minutes",
        "estimated_cost",
    ):
        setattr(recipe, field, data[field])

    existing = {item.ingredient.name: item for item in recipe.ingredients}
    expected_names = set(data["ingredients"])
    missing = sorted(expected_names - ingredients_by_name.keys())
    if missing:
        raise ValueError(f"Unknown ingredients for {data['name']}: {missing}")
    for name in expected_names - existing.keys():
        recipe.ingredients.append(RecipeIngredient(ingredient=ingredients_by_name[name]))
    for name in existing.keys() - expected_names:
        session.delete(existing[name])
    return recipe


def seed_database(
    session: Session,
    ingredients: Sequence[IngredientSeed] = INGREDIENTS,
    recipes: Sequence[RecipeSeed] = RECIPES,
) -> tuple[int, int]:
    ingredients_by_name = {data["name"]: _seed_ingredient(session, data) for data in ingredients}
    session.flush()
    for data in recipes:
        _seed_recipe(session, data, ingredients_by_name)
    session.commit()
    return len(ingredients), len(recipes)


def main() -> None:
    with SessionLocal() as session:
        ingredient_count, recipe_count = seed_database(session)
    print(f"Seeded {ingredient_count} ingredients and {recipe_count} recipes.")


if __name__ == "__main__":
    main()
