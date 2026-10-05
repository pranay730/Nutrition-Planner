import uuid
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import TimestampMixin


class Recipe(TimestampMixin, Base):
    __tablename__ = "recipes"
    __table_args__ = (
        CheckConstraint("calories > 0", name="positive_calories"),
        CheckConstraint("protein_g >= 0", name="nonnegative_protein"),
        CheckConstraint("carbs_g >= 0", name="nonnegative_carbs"),
        CheckConstraint("fat_g >= 0", name="nonnegative_fat"),
        CheckConstraint("preparation_minutes > 0", name="positive_preparation_minutes"),
        CheckConstraint("estimated_cost >= 0", name="nonnegative_estimated_cost"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(160), unique=True, index=True)
    description: Mapped[str | None] = mapped_column(Text)
    cuisine: Mapped[str] = mapped_column(String(64), index=True)
    meal_type: Mapped[str] = mapped_column(String(32), index=True)
    calories: Mapped[int] = mapped_column(Integer)
    protein_g: Mapped[Decimal] = mapped_column(Numeric(6, 2))
    carbs_g: Mapped[Decimal] = mapped_column(Numeric(6, 2))
    fat_g: Mapped[Decimal] = mapped_column(Numeric(6, 2))
    preparation_minutes: Mapped[int] = mapped_column(Integer)
    estimated_cost: Mapped[Decimal] = mapped_column(Numeric(8, 2))

    ingredients: Mapped[list["RecipeIngredient"]] = relationship(
        back_populates="recipe", cascade="all, delete-orphan"
    )


class RecipeIngredient(Base):
    __tablename__ = "recipe_ingredients"
    __table_args__ = (UniqueConstraint("recipe_id", "ingredient_id"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    recipe_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("recipes.id", ondelete="CASCADE"), index=True
    )
    ingredient_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("ingredients.id", ondelete="RESTRICT"), index=True
    )
    quantity_text: Mapped[str | None] = mapped_column(String(80))
    is_optional: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")

    recipe: Mapped[Recipe] = relationship(back_populates="ingredients")
    ingredient: Mapped["Ingredient"] = relationship(back_populates="recipe_ingredients")


from app.models.ingredient import Ingredient  # noqa: E402
