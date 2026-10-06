from collections.abc import Iterator
from typing import Any

import pytest
from argon2 import PasswordHasher
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.main import create_app
from app.models import User
from tests.helpers import make_sqlite_session

PASSWORD = "correct horse battery staple"


@pytest.fixture
def auth_client() -> Iterator[tuple[TestClient, Session]]:
    session = make_sqlite_session()
    application = create_app()

    def override_database() -> Iterator[Session]:
        yield session

    application.dependency_overrides[get_db] = override_database
    with TestClient(application) as client:
        yield client, session
    session.close()


def register(client: TestClient, email: str = "pat@example.com") -> dict[str, Any]:
    response = client.post("/auth/register", json={"email": email, "password": PASSWORD})
    assert response.status_code == 201
    return response.json()


def auth_header(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def test_registration_hashes_password_and_returns_access_token(
    auth_client: tuple[TestClient, Session],
) -> None:
    client, session = auth_client

    body = register(client, "Pat@Example.com")
    user = session.scalar(select(User).where(User.email == "pat@example.com"))

    assert body["token_type"] == "bearer"
    assert body["access_token"]
    assert body["user"]["email"] == "pat@example.com"
    assert "password" not in body["user"]
    assert user is not None
    assert user.password_hash != PASSWORD
    assert user.password_hash.startswith("$argon2id$")


def test_duplicate_registration_is_rejected(
    auth_client: tuple[TestClient, Session],
) -> None:
    client, _ = auth_client
    register(client, "pat@example.com")

    response = client.post(
        "/auth/register",
        json={"email": "PAT@example.com", "password": "a different secure password"},
    )

    assert response.status_code == 409


def test_registration_rejects_short_password(auth_client: tuple[TestClient, Session]) -> None:
    client, _ = auth_client
    response = client.post(
        "/auth/register", json={"email": "pat@example.com", "password": "too-short"}
    )

    assert response.status_code == 422


def test_login_with_valid_credentials(auth_client: tuple[TestClient, Session]) -> None:
    client, _ = auth_client
    register(client)

    response = client.post("/auth/login", json={"email": "PAT@example.com", "password": PASSWORD})

    assert response.status_code == 200
    assert response.json()["access_token"]
    assert response.json()["user"]["email"] == "pat@example.com"


def test_login_upgrades_outdated_password_hash(
    auth_client: tuple[TestClient, Session],
) -> None:
    client, session = auth_client
    register(client)
    user = session.scalar(select(User).where(User.email == "pat@example.com"))
    assert user is not None
    outdated_hash = PasswordHasher(time_cost=1, memory_cost=8192, parallelism=1).hash(PASSWORD)
    user.password_hash = outdated_hash
    session.commit()

    response = client.post("/auth/login", json={"email": user.email, "password": PASSWORD})

    session.refresh(user)
    assert response.status_code == 200
    assert user.password_hash != outdated_hash


@pytest.mark.parametrize(
    ("email", "password"),
    [
        ("missing@example.com", PASSWORD),
        ("pat@example.com", "the wrong password"),
    ],
)
def test_login_rejects_invalid_credentials(
    auth_client: tuple[TestClient, Session], email: str, password: str
) -> None:
    client, _ = auth_client
    register(client)

    response = client.post("/auth/login", json={"email": email, "password": password})

    assert response.status_code == 401
    assert response.json() == {"detail": "Invalid email or password"}
    assert response.headers["www-authenticate"] == "Bearer"


def test_users_me_requires_authentication(auth_client: tuple[TestClient, Session]) -> None:
    client, _ = auth_client
    response = client.get("/users/me")

    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"


def test_users_me_returns_only_token_owner(auth_client: tuple[TestClient, Session]) -> None:
    client, _ = auth_client
    first = register(client, "first@example.com")
    second = register(client, "second@example.com")

    first_response = client.get("/users/me", headers=auth_header(first["access_token"]))
    second_response = client.get("/users/me", headers=auth_header(second["access_token"]))

    assert first_response.status_code == second_response.status_code == 200
    assert first_response.json()["email"] == "first@example.com"
    assert second_response.json()["email"] == "second@example.com"
    assert first_response.json()["id"] != second_response.json()["id"]


def test_token_for_deleted_user_is_rejected(auth_client: tuple[TestClient, Session]) -> None:
    client, session = auth_client
    body = register(client)
    user = session.scalar(select(User).where(User.email == "pat@example.com"))
    assert user is not None
    session.delete(user)
    session.commit()

    response = client.get("/users/me", headers=auth_header(body["access_token"]))

    assert response.status_code == 401


def test_tampered_token_is_rejected(auth_client: tuple[TestClient, Session]) -> None:
    client, _ = auth_client
    body = register(client)
    header, payload, signature = body["access_token"].split(".")
    altered_signature = f"{'a' if signature[0] != 'a' else 'b'}{signature[1:]}"
    tampered = ".".join((header, payload, altered_signature))

    response = client.get("/users/me", headers=auth_header(tampered))

    assert response.status_code == 401
