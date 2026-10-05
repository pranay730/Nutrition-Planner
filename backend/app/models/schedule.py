import uuid
from datetime import time

from sqlalchemy import CheckConstraint, ForeignKey, String, Time, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import TimestampMixin


class MealSchedule(TimestampMixin, Base):
    __tablename__ = "meal_schedules"
    __table_args__ = (
        UniqueConstraint("user_id", "meal_type"),
        CheckConstraint(
            "reminder_minutes_before BETWEEN 0 AND 180", name="reminder_lead_time_range"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    meal_type: Mapped[str] = mapped_column(String(32))
    preferred_time: Mapped[time] = mapped_column(Time)
    reminder_minutes_before: Mapped[int] = mapped_column(default=15, server_default="15")
    reminder_enabled: Mapped[bool] = mapped_column(default=True, server_default="true")

    user: Mapped["User"] = relationship(back_populates="meal_schedules")


from app.models.user import User  # noqa: E402
