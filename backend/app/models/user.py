import uuid

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import TimestampMixin


class User(TimestampMixin, Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))

    profile: Mapped["Profile | None"] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    cuisine_preferences: Mapped[list["CuisinePreference"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    meal_schedules: Mapped[list["MealSchedule"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    pantry_items: Mapped[list["PantryItem"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    meal_logs: Mapped[list["MealLog"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    notifications: Mapped[list["Notification"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )


from app.models.meal import MealLog  # noqa: E402
from app.models.notification import Notification  # noqa: E402
from app.models.pantry import PantryItem  # noqa: E402
from app.models.profile import CuisinePreference, Profile  # noqa: E402
from app.models.schedule import MealSchedule  # noqa: E402
