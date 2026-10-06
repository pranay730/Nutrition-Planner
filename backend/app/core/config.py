from functools import lru_cache

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Nutrition Planner API"
    environment: str = "development"
    database_url: str = "postgresql+psycopg://nutrition:nutrition_dev@localhost:5432/nutrition"
    redis_url: str = "redis://localhost:6379/0"
    celery_broker_url: str = "redis://localhost:6379/0"
    celery_result_backend: str = "redis://localhost:6379/1"
    jwt_secret_key: str = Field(default="development-only-change-me-please", min_length=32)
    jwt_algorithm: str = "HS256"
    jwt_issuer: str = "nutrition-planner-api"
    jwt_audience: str = "nutrition-planner-web"
    access_token_expire_minutes: int = Field(default=30, gt=0)

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    @model_validator(mode="after")
    def validate_production_secret(self) -> "Settings":
        if self.environment.casefold() == "production" and self.jwt_secret_key == (
            "development-only-change-me-please"
        ):
            raise ValueError("JWT_SECRET_KEY must be configured in production")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
