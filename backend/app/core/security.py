import uuid
from datetime import UTC, datetime, timedelta

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError

from app.core.config import Settings, get_settings

password_hasher = PasswordHasher()


class InvalidTokenError(ValueError):
    pass


def hash_password(password: str) -> str:
    return password_hasher.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return password_hasher.verify(password_hash, password)
    except (InvalidHashError, VerificationError):
        return False


def password_needs_rehash(password_hash: str) -> bool:
    try:
        return password_hasher.check_needs_rehash(password_hash)
    except InvalidHashError:
        return True


def create_access_token(
    user_id: uuid.UUID,
    *,
    settings: Settings | None = None,
    now: datetime | None = None,
) -> str:
    active_settings = settings or get_settings()
    issued_at = now or datetime.now(UTC)
    expires_at = issued_at + timedelta(minutes=active_settings.access_token_expire_minutes)
    payload = {
        "sub": str(user_id),
        "type": "access",
        "iat": issued_at,
        "exp": expires_at,
        "iss": active_settings.jwt_issuer,
        "aud": active_settings.jwt_audience,
    }
    return jwt.encode(
        payload,
        active_settings.jwt_secret_key,
        algorithm=active_settings.jwt_algorithm,
    )


def decode_access_token(token: str, *, settings: Settings | None = None) -> uuid.UUID:
    active_settings = settings or get_settings()
    try:
        payload = jwt.decode(
            token,
            active_settings.jwt_secret_key,
            algorithms=[active_settings.jwt_algorithm],
            issuer=active_settings.jwt_issuer,
            audience=active_settings.jwt_audience,
            options={"require": ["sub", "type", "iat", "exp", "iss", "aud"]},
        )
        if payload.get("type") != "access":
            raise InvalidTokenError("Token is not an access token")
        return uuid.UUID(payload["sub"])
    except (KeyError, TypeError, ValueError, jwt.InvalidTokenError) as exc:
        raise InvalidTokenError("Invalid access token") from exc
