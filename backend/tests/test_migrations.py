import os
from collections.abc import Iterator
from pathlib import Path

import pytest
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, func, inspect, select, text
from sqlalchemy.engine import Engine
from sqlalchemy.engine.url import make_url
from sqlalchemy.orm import Session

from alembic import command
from app import models as _models  # noqa: F401
from app.core.config import get_settings
from app.core.database import Base, get_db
from app.main import create_app
from app.models import Ingredient, IngredientCuisineTag, Recipe, RecipeIngredient, User
from app.seed import seed_database
from app.seed_data import INGREDIENTS, RECIPES

BACKEND_DIR = Path(__file__).resolve().parents[1]
DEFAULT_TEST_DATABASE_URL = (
    "postgresql+psycopg://nutrition:nutrition_dev@localhost:5432/nutrition_test"
)
EXPECTED_TABLES = {
    "cuisine_preferences",
    "ingredient_cuisine_tags",
    "ingredients",
    "meal_logs",
    "meal_schedules",
    "notifications",
    "pantry_items",
    "profiles",
    "recipe_ingredients",
    "recipes",
    "users",
}


def _alembic_config(database_url: str) -> Config:
    config = Config(str(BACKEND_DIR / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND_DIR / "alembic"))
    config.set_main_option("sqlalchemy.url", database_url)
    return config


def _ensure_database(database_url: str) -> None:
    url = make_url(database_url)
    if url.database is None:
        raise ValueError("TEST_DATABASE_URL must include a database name")

    admin_engine = create_engine(url.set(database="postgres"), isolation_level="AUTOCOMMIT")
    try:
        with admin_engine.connect() as connection:
            exists = connection.execute(
                text("SELECT 1 FROM pg_database WHERE datname = :name"),
                {"name": url.database},
            ).scalar()
            if exists is None:
                connection.execute(text(f'CREATE DATABASE "{url.database}"'))
    finally:
        admin_engine.dispose()


@pytest.fixture(scope="module")
def postgres_url() -> Iterator[str]:
    database_url = os.environ.get("TEST_DATABASE_URL", DEFAULT_TEST_DATABASE_URL)
    try:
        _ensure_database(database_url)
        engine = create_engine(database_url)
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        engine.dispose()
    except Exception as exc:
        pytest.skip(f"PostgreSQL is not available: {exc}")

    previous_url = os.environ.get("DATABASE_URL")
    os.environ["DATABASE_URL"] = database_url
    get_settings.cache_clear()
    try:
        yield database_url
    finally:
        if previous_url is None:
            os.environ.pop("DATABASE_URL", None)
        else:
            os.environ["DATABASE_URL"] = previous_url
        get_settings.cache_clear()


@pytest.fixture
def postgres_engine(postgres_url: str, monkeypatch: pytest.MonkeyPatch) -> Iterator[Engine]:
    monkeypatch.chdir(BACKEND_DIR)
    engine = create_engine(postgres_url)
    try:
        yield engine
    finally:
        engine.dispose()


def _metadata_diffs(engine: Engine) -> list[object]:
    with engine.connect() as connection:
        context = MigrationContext.configure(connection, opts={"compare_type": True})
        return compare_metadata(context, Base.metadata)


@pytest.mark.postgres
def test_postgres_migrate_seed_and_metadata_parity(
    postgres_engine: Engine, postgres_url: str
) -> None:
    config = _alembic_config(postgres_url)

    command.upgrade(config, "head")
    inspector = inspect(postgres_engine)
    assert EXPECTED_TABLES <= set(inspector.get_table_names())
    assert _metadata_diffs(postgres_engine) == []

    with Session(postgres_engine) as session:
        first = seed_database(session)
        second = seed_database(session)
        ingredient_count = session.scalar(select(func.count()).select_from(Ingredient))
        recipe_count = session.scalar(select(func.count()).select_from(Recipe))
        tag_count = session.scalar(select(func.count()).select_from(IngredientCuisineTag))
        recipe_ingredient_count = session.scalar(select(func.count()).select_from(RecipeIngredient))

    assert first == second == (len(INGREDIENTS), len(RECIPES))
    assert ingredient_count == len(INGREDIENTS)
    assert recipe_count == len(RECIPES)
    assert tag_count and tag_count > len(INGREDIENTS)
    assert recipe_ingredient_count == sum(len(recipe["ingredients"]) for recipe in RECIPES)

    command.downgrade(config, "base")
    remaining = set(inspect(postgres_engine).get_table_names()) - {"alembic_version"}
    assert remaining == set()

    command.upgrade(config, "head")
    assert EXPECTED_TABLES <= set(inspect(postgres_engine).get_table_names())
    assert _metadata_diffs(postgres_engine) == []


@pytest.mark.postgres
def test_authentication_flow_uses_postgres(postgres_engine: Engine, postgres_url: str) -> None:
    command.upgrade(_alembic_config(postgres_url), "head")
    application = create_app()

    def override_database() -> Iterator[Session]:
        with Session(postgres_engine) as session:
            yield session

    application.dependency_overrides[get_db] = override_database
    email = "postgres-auth-gate@example.com"
    password = "correct horse battery staple"

    with Session(postgres_engine) as session:
        existing = session.scalar(select(User).where(User.email == email))
        if existing is not None:
            session.delete(existing)
            session.commit()

    with TestClient(application) as client:
        registration = client.post(
            "/auth/register", json={"email": email, "password": password}
        )
        assert registration.status_code == 201

        login = client.post("/auth/login", json={"email": email, "password": password})
        assert login.status_code == 200

        current_user = client.get(
            "/users/me",
            headers={"Authorization": f"Bearer {login.json()['access_token']}"},
        )
        assert current_user.status_code == 200
        assert current_user.json()["email"] == email
