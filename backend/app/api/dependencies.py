from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import InvalidTokenError, decode_access_token
from app.models import User
from app.users.repository import UserRepository

bearer_scheme = HTTPBearer(auto_error=False)
DatabaseSession = Annotated[Session, Depends(get_db)]


def authentication_error() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )


def get_current_user(
    db: DatabaseSession,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
) -> User:
    if credentials is None or credentials.scheme.casefold() != "bearer":
        raise authentication_error()
    try:
        user_id = decode_access_token(credentials.credentials)
    except InvalidTokenError as exc:
        raise authentication_error() from exc

    user = UserRepository(db).get_by_id(user_id)
    if user is None:
        raise authentication_error()
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]
