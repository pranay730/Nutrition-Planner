from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.security import (
    create_access_token,
    hash_password,
    password_needs_rehash,
    verify_password,
)
from app.models import User
from app.users.repository import UserRepository

DUMMY_PASSWORD_HASH = hash_password("not-a-real-user-password")


class EmailAlreadyRegisteredError(ValueError):
    pass


class InvalidCredentialsError(ValueError):
    pass


def normalize_email(email: str) -> str:
    return email.strip().casefold()


class AuthService:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.users = UserRepository(session)

    def register(self, email: str, password: str) -> tuple[User, str]:
        normalized_email = normalize_email(email)
        if self.users.get_by_email(normalized_email) is not None:
            raise EmailAlreadyRegisteredError

        user = User(email=normalized_email, password_hash=hash_password(password))
        self.users.add(user)
        try:
            self.session.commit()
        except IntegrityError as exc:
            self.session.rollback()
            raise EmailAlreadyRegisteredError from exc
        self.session.refresh(user)
        return user, create_access_token(user.id)

    def login(self, email: str, password: str) -> tuple[User, str]:
        user = self.users.get_by_email(normalize_email(email))
        if user is None:
            verify_password(password, DUMMY_PASSWORD_HASH)
            raise InvalidCredentialsError
        if not verify_password(password, user.password_hash):
            raise InvalidCredentialsError

        if password_needs_rehash(user.password_hash):
            user.password_hash = hash_password(password)
            self.session.commit()
            self.session.refresh(user)
        return user, create_access_token(user.id)
