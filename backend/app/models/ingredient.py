import uuid

from sqlalchemy import ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import TimestampMixin


class Ingredient(TimestampMixin, Base):
    __tablename__ = "ingredients"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    category: Mapped[str] = mapped_column(String(64), index=True)

    cuisine_tags: Mapped[list["IngredientCuisineTag"]] = relationship(
        back_populates="ingredient", cascade="all, delete-orphan"
    )
    pantry_items: Mapped[list["PantryItem"]] = relationship(back_populates="ingredient")
    recipe_ingredients: Mapped[list["RecipeIngredient"]] = relationship(back_populates="ingredient")


class IngredientCuisineTag(Base):
    __tablename__ = "ingredient_cuisine_tags"
    __table_args__ = (UniqueConstraint("ingredient_id", "cuisine"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    ingredient_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("ingredients.id", ondelete="CASCADE"), index=True
    )
    cuisine: Mapped[str] = mapped_column(String(64), index=True)

    ingredient: Mapped[Ingredient] = relationship(back_populates="cuisine_tags")


from app.models.pantry import PantryItem  # noqa: E402
from app.models.recipe import RecipeIngredient  # noqa: E402
