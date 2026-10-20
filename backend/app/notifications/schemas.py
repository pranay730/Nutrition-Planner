import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models.enums import NotificationStatus


class NotificationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    meal_type: str | None
    title: str
    body: str
    status: NotificationStatus
    scheduled_for: datetime | None
    generated_at: datetime | None
    read_at: datetime | None


class NotificationListResponse(BaseModel):
    notifications: list[NotificationResponse]


class NotificationUpdate(BaseModel):
    read: bool
