# Nutrition Planner

A production-oriented modular monolith that recommends what a user should eat next based on their daily calorie budget, meal schedule, preferences, pantry, and meal history.

This repository currently contains the foundation, persistence, authentication, and onboarding phases: React/Vite, FastAPI, PostgreSQL, Redis, Celery, Docker Compose, normalized SQLAlchemy models, Alembic migrations, canonical recipe seed data, JWT authentication, calculated calorie targets, cuisine preferences, ingredient suggestions, and meal schedules. Product APIs described in [PLAN.md](PLAN.md) remain intentionally phased.

## Prerequisites

- Docker with Docker Compose v2
- Optional for non-container development: Python 3.12+ and Node.js 22+

## Start the development environment

Copy the environment template, then start all services:

```bash
cp .env.example .env
docker compose up --build
```

Services:

- Frontend: <http://localhost:5173>
- Backend API: <http://localhost:8000>
- OpenAPI docs: <http://localhost:8000/docs>
- Health check: <http://localhost:8000/health>
- PostgreSQL: `localhost:5432`
- Redis: `localhost:6379`

Stop services with `docker compose down`. Add `--volumes` only when you intentionally want to delete local database data.

## Backend development without Docker

Start PostgreSQL and Redis (Docker can run only those dependencies):

```bash
docker compose up -d postgres redis
```

Create a virtual environment and install the backend:

```bash
cd backend
python3.12 -m venv .venv
source .venv/bin/activate
pip install -e '.[dev]'
```

When the API runs on the host, provide host-local service URLs:

```bash
export DATABASE_URL=postgresql+psycopg://nutrition:nutrition_dev@localhost:5432/nutrition
export REDIS_URL=redis://localhost:6379/0
export CELERY_BROKER_URL=redis://localhost:6379/0
export CELERY_RESULT_BACKEND=redis://localhost:6379/1
uvicorn app.main:app --reload
```

Run backend checks:

```bash
pytest
ruff check .
```

`pytest` always runs SQLite persistence, seed, constraint, foreign-key, authentication, onboarding, and daily-state tests. PostgreSQL tests skip unless the database is reachable. To run the full Phase 2 through Phase 5 gate, start Postgres and point tests at an isolated database:

```bash
docker compose up -d postgres
cd backend
TEST_DATABASE_URL=postgresql+psycopg://nutrition:nutrition_dev@localhost:5432/nutrition_test pytest
```

The Postgres suite upgrades, seeds twice, compares Alembic history to SQLAlchemy metadata, downgrades and re-upgrades, then exercises authentication, onboarding, meal logging, and daily planning. It uses `nutrition_test` so it does not wipe local development data.

## Frontend development without Docker

```bash
cd frontend
npm install
npm run dev
```

## Database migrations and seed data

With the Compose stack running, apply migrations and seed the canonical ingredient/recipe data:

```bash
docker compose exec backend alembic upgrade head
docker compose exec backend seed-db
```

The seed command is idempotent and can be rerun after seed-data changes. Useful migration commands:

```bash
docker compose exec backend alembic current
docker compose exec backend alembic history
docker compose exec backend alembic downgrade base
```

For host-based backend development, run the equivalent commands from `backend/` using `alembic` and `seed-db` after exporting the host-local `DATABASE_URL` shown above.

## Authentication API

Phase 3 provides JSON email/password authentication. Passwords require at least 12 characters and are stored only as Argon2id hashes.

```bash
curl -X POST http://localhost:8000/auth/register \
  -H 'Content-Type: application/json' \
  -d '{"email":"developer@example.com","password":"correct horse battery staple"}'

curl -X POST http://localhost:8000/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"email":"developer@example.com","password":"correct horse battery staple"}'

curl http://localhost:8000/users/me \
  -H 'Authorization: Bearer YOUR_ACCESS_TOKEN'
```

Access tokens expire after 30 minutes by default. Set a unique `JWT_SECRET_KEY` of at least 32 characters in every shared environment; the application rejects the development placeholder when `ENVIRONMENT=production`.

## Onboarding API

All onboarding routes require the bearer token returned by registration or login. A profile stores validated health inputs and an IANA timezone; the server calculates the daily calorie target using the Mifflin-St Jeor equation, activity multiplier, and goal adjustment.

```bash
curl -X PUT http://localhost:8000/onboarding/profile \
  -H 'Authorization: Bearer YOUR_ACCESS_TOKEN' \
  -H 'Content-Type: application/json' \
  -d '{"age":30,"calculation_sex":"female","height_cm":170,"weight_kg":70,"activity_level":"moderate","goal_type":"maintain_weight","timezone":"America/Indiana/Indianapolis"}'

curl -X PUT http://localhost:8000/preferences/cuisines \
  -H 'Authorization: Bearer YOUR_ACCESS_TOKEN' \
  -H 'Content-Type: application/json' \
  -d '{"cuisines":["Indian","Italian"]}'

curl http://localhost:8000/ingredients/suggestions \
  -H 'Authorization: Bearer YOUR_ACCESS_TOKEN'

curl -X PUT http://localhost:8000/meal-schedules \
  -H 'Authorization: Bearer YOUR_ACCESS_TOKEN' \
  -H 'Content-Type: application/json' \
  -d '{"schedules":[{"meal_type":"breakfast","preferred_time":"08:00:00"},{"meal_type":"dinner","preferred_time":"18:30:00","reminder_minutes_before":30}]}'
```

Cuisine preferences and meal schedules use replace semantics: each successful request becomes the user's complete current set. Ingredient suggestions are ranked by how many selected cuisines match each canonical ingredient.

## Daily-state API

Meal timestamps must include a timezone offset and are normalized to UTC. The “today” endpoints use the timezone stored during onboarding, including daylight-saving transitions.

```bash
curl -X POST http://localhost:8000/meals \
  -H 'Authorization: Bearer YOUR_ACCESS_TOKEN' \
  -H 'Content-Type: application/json' \
  -d '{"meal_type":"lunch","food_name":"Chickpea rice bowl","calories":560}'

curl http://localhost:8000/meals/today \
  -H 'Authorization: Bearer YOUR_ACCESS_TOKEN'

curl http://localhost:8000/daily-plan \
  -H 'Authorization: Bearer YOUR_ACCESS_TOKEN'
```

The daily plan derives consumed calories and the signed target-minus-consumed balance without storing duplicate totals. A positive balance is distributed exactly across upcoming schedule entries whose meal type has not already been logged today; over-target days report a negative balance and zero allocations.

## Configuration

Configuration is loaded from environment variables. `.env.example` contains development-safe defaults; copy it to `.env` and replace `JWT_SECRET_KEY` before any shared or deployed environment. Never commit `.env` or production secrets.

## Project status

See [task_plan.md](task_plan.md) for the live implementation checklist and [PLAN.md](PLAN.md) for architecture, API, persistence, and phased delivery decisions.
