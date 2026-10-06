import uuid
from datetime import UTC, datetime, timedelta

import jwt
import pytest

from app.core.config import Settings
from app.core.security import InvalidTokenError, create_access_token, decode_access_token


def test_access_token_round_trip() -> None:
    user_id = uuid.uuid4()
    settings = Settings(jwt_secret_key="test-secret-key-that-is-long-enough")

    token = create_access_token(user_id, settings=settings)

    assert decode_access_token(token, settings=settings) == user_id


def test_expired_access_token_is_rejected() -> None:
    settings = Settings(
        jwt_secret_key="test-secret-key-that-is-long-enough",
        access_token_expire_minutes=1,
    )
    token = create_access_token(
        uuid.uuid4(), settings=settings, now=datetime(2000, 1, 1, tzinfo=UTC)
    )

    with pytest.raises(InvalidTokenError):
        decode_access_token(token, settings=settings)


def test_access_token_requires_expiry_claim() -> None:
    settings = Settings(jwt_secret_key="test-secret-key-that-is-long-enough")
    now = datetime.now(UTC)
    token = jwt.encode(
        {
            "sub": str(uuid.uuid4()),
            "type": "access",
            "iat": now,
            "iss": settings.jwt_issuer,
            "aud": settings.jwt_audience,
        },
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
    )

    with pytest.raises(InvalidTokenError):
        decode_access_token(token, settings=settings)


def test_access_token_rejects_wrong_audience() -> None:
    settings = Settings(jwt_secret_key="test-secret-key-that-is-long-enough")
    now = datetime.now(UTC)
    token = jwt.encode(
        {
            "sub": str(uuid.uuid4()),
            "type": "access",
            "iat": now,
            "exp": now + timedelta(minutes=5),
            "iss": settings.jwt_issuer,
            "aud": "another-application",
        },
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
    )

    with pytest.raises(InvalidTokenError):
        decode_access_token(token, settings=settings)


def test_production_rejects_default_jwt_secret() -> None:
    with pytest.raises(ValueError, match="JWT_SECRET_KEY"):
        Settings(environment="production", jwt_secret_key="development-only-change-me-please")
