from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.main import create_app
from app.models import Ingredient, PantryItem, User
from app.seed import seed_database
from tests.helpers import make_sqlite_session

PASSWORD = "correct horse battery staple"


@pytest.fixture
def pantry_client() -> Iterator[tuple[TestClient, Session]]:
    session = make_sqlite_session()
    seed_database(session)
    application = create_app()

    def override_database() -> Iterator[Session]:
        yield session

    application.dependency_overrides[get_db] = override_database
    with TestClient(application) as client:
        yield client, session
    session.close()


def _register(client: TestClient, email: str) -> dict[str, str]:
    response = client.post("/auth/register", json={"email": email, "password": PASSWORD})
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def test_pantry_items_are_owner_scoped_and_upserted(
    pantry_client: tuple[TestClient, Session],
) -> None:
    client, session = pantry_client
    owner = _register(client, "owner@example.com")
    other = _register(client, "other@example.com")
    ingredient = session.scalar(select(Ingredient).order_by(Ingredient.name))
    assert ingredient is not None

    created = client.put(
        f"/pantry/{ingredient.id}", json={"status": "available"}, headers=owner
    )
    updated = client.put(f"/pantry/{ingredient.id}", json={"status": "low"}, headers=owner)

    assert created.status_code == updated.status_code == 200
    assert updated.json()["status"] == "low"
    assert client.get("/pantry", headers=other).json() == []
    assert session.scalar(select(func.count()).select_from(PantryItem)) == 1


def test_replace_pantry_validates_ingredients_and_replaces_the_owner_set(
    pantry_client: tuple[TestClient, Session],
) -> None:
    client, session = pantry_client
    headers = _register(client, "owner@example.com")
    ingredients = session.scalars(select(Ingredient).order_by(Ingredient.name).limit(2)).all()
    payload = {
        "items": [
            {"ingredient_id": str(ingredients[0].id), "status": "available"},
            {"ingredient_id": str(ingredients[1].id), "status": "low"},
        ]
    }

    first = client.put("/pantry", json=payload, headers=headers)
    second = client.put("/pantry", json={"items": [payload["items"][1]]}, headers=headers)

    assert first.status_code == second.status_code == 200
    assert [item["ingredient_id"] for item in second.json()] == [str(ingredients[1].id)]
    assert session.scalar(select(func.count()).select_from(PantryItem)) == 1


def test_pantry_rejects_unknown_ingredient_and_requires_authentication(
    pantry_client: tuple[TestClient, Session],
) -> None:
    client, session = pantry_client
    headers = _register(client, "owner@example.com")
    user_id = session.scalar(select(User.id).where(User.email == "owner@example.com"))
    assert user_id is not None

    unknown = client.put(
        "/pantry/00000000-0000-0000-0000-000000000000",
        json={"status": "available"},
        headers=headers,
    )

    assert unknown.status_code == 404
    assert client.get("/pantry").status_code == 401
