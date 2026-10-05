import uuid
from datetime import date
from decimal import Decimal

from sqlalchemy import (
    CheckConstraint,
    Date,
    Enum,
    ForeignKey,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import TimestampMixin
from app.models.enums import ActivityLevel, GoalType, enum_values


class Profile(TimestampMixin, Base):
    __tablename__ = "profiles"
    __table_args__ = (
        CheckConstraint("age BETWEEN 13 AND 120", name="age_range"),
        CheckConstraint("height_cm BETWEEN 80 AND 250", name="height_range"),
        CheckConstraint("weight_kg BETWEEN 25 AND 500", name="weight_range"),
        CheckConstraint(
            "goal_weight_kg IS NULL OR goal_weight_kg BETWEEN 25 AND 500",
            name="goal_weight_range",
        ),
        CheckConstraint("daily_calorie_target BETWEEN 800 AND 10000", name="calorie_target_range"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), unique=True, index=True
    )
    age: Mapped[int] = mapped_column(Integer)
    height_cm: Mapped[Decimal] = mapped_column(Numeric(5, 2))
    weight_kg: Mapped[Decimal] = mapped_column(Numeric(6, 2))
    activity_level: Mapped[ActivityLevel] = mapped_column(
        Enum(
            ActivityLevel,
            values_callable=enum_values,
            native_enum=False,
            create_constraint=True,
            length=32,
        )
    )
    goal_type: Mapped[GoalType] = mapped_column(
        Enum(
            GoalType,
            values_callable=enum_values,
            native_enum=False,
            create_constraint=True,
            length=32,
        )
    )
    goal_weight_kg: Mapped[Decimal | None] = mapped_column(Numeric(6, 2))
    target_date: Mapped[date | None] = mapped_column(Date)
    daily_calorie_target: Mapped[int] = mapped_column(Integer)
    timezone: Mapped[str] = mapped_column(String(64), default="UTC", server_default="UTC")

    user: Mapped["User"] = relationship(back_populates="profile")


class CuisinePreference(TimestampMixin, Base):
    __tablename__ = "cuisine_preferences"
    __table_args__ = (UniqueConstraint("user_id", "cuisine"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    cuisine: Mapped[str] = mapped_column(String(64))

    user: Mapped["User"] = relationship(back_populates="cuisine_preferences")


from app.models.user import User  # noqa: E402
