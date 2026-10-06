from fastapi import APIRouter

from app.api.routes.auth import router as auth_router
from app.api.routes.health import router as health_router
from app.api.routes.users import router as users_router
from app.meals.routes import router as meals_router
from app.onboarding.routes import router as onboarding_router
from app.pantry.routes import router as ingredients_router
from app.preferences import router as preferences_router
from app.schedules.routes import router as schedules_router
from app.services.daily_plan import router as daily_plan_router

api_router = APIRouter()
api_router.include_router(health_router)
api_router.include_router(auth_router)
api_router.include_router(users_router)
api_router.include_router(onboarding_router)
api_router.include_router(preferences_router)
api_router.include_router(ingredients_router)
api_router.include_router(schedules_router)
api_router.include_router(meals_router)
api_router.include_router(daily_plan_router)
