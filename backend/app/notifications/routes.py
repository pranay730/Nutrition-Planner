import uuid
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, status

from app.api.dependencies import CurrentUser, DatabaseSession
from app.notifications.schemas import (
    NotificationListResponse,
    NotificationResponse,
    NotificationUpdate,
)
from app.notifications.service import ReminderService

router = APIRouter(prefix="/notifications", tags=["notifications"])


@router.get("", response_model=NotificationListResponse)
def list_notifications(
    current_user: CurrentUser,
    db: DatabaseSession,
    unread_only: bool = False,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> NotificationListResponse:
    notifications = ReminderService(db).list_for_user(
        current_user.id, unread_only=unread_only, limit=limit
    )
    return NotificationListResponse(notifications=notifications)


@router.patch("/{notification_id}", response_model=NotificationResponse)
def update_notification(
    notification_id: uuid.UUID,
    payload: NotificationUpdate,
    current_user: CurrentUser,
    db: DatabaseSession,
) -> NotificationResponse:
    notification = ReminderService(db).set_read(
        current_user.id, notification_id, read=payload.read
    )
    if notification is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Notification not found")
    return NotificationResponse.model_validate(notification)
