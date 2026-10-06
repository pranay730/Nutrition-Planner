import uuid
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import MealLog


class MealRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def add(self, meal: MealLog) -> MealLog:
        self.session.add(meal)
        return meal

    def list_between(
        self, user_id: uuid.UUID, start: datetime, end: datetime
    ) -> list[MealLog]:
        return list(
            self.session.scalars(
                select(MealLog)
                .where(
                    MealLog.user_id == user_id,
                    MealLog.occurred_at >= start,
                    MealLog.occurred_at < end,
                )
                .order_by(MealLog.occurred_at, MealLog.created_at, MealLog.id)
            ).all()
        )
