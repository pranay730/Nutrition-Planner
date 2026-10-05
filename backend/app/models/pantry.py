import uuid

from sqlalchemy import Enum, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import TimestampMixin
from app.models.enums import PantryStatus, enum_values


class PantryItem(TimestampMixin, Base):
    __tablename__ = "pantry_items"
    __table_args__ = (UniqueConstraint("user_id", "ingredient_id"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    ingredient_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("ingredients.id", ondelete="CASCADE"), index=True
    )
    status: Mapped[PantryStatus] = mapped_column(
        Enum(
            PantryStatus,
            values_callable=enum_values,
            native_enum=False,
            create_constraint=True,
            length=20,
        ),
        default=PantryStatus.AVAILABLE,
        server_default=PantryStatus.AVAILABLE.value,
    )

    user: Mapped["User"] = relationship(back_populates="pantry_items")
    ingredient: Mapped["Ingredient"] = relationship(back_populates="pantry_items")


from app.models.ingredient import Ingredient  # noqa: E402
from app.models.user import User  # noqa: E402
