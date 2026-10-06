# Nutrition Planner

A production-oriented modular monolith that recommends what a user should eat next based on their daily calorie budget, meal schedule, preferences, pantry, and meal history.

This repository currently contains the Phase 1 foundation, Phase 2 persistence layer, and Phase 3 authentication API: React/Vite, FastAPI, PostgreSQL, Redis, Celery, Docker Compose, normalized SQLAlchemy models, Alembic migrations, canonical recipe seed data, and JWT-based authentication. Product APIs described in [PLAN.md](PLAN.md) remain intentionally phased.

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

`pytest` always runs SQLite persistence, seed, constraint, foreign-key, and authentication tests. PostgreSQL tests skip unless the database is reachable. To run the full Phase 2 and Phase 3 gate, start Postgres and point tests at an isolated database:

```bash
docker compose up -d postgres
cd backend
TEST_DATABASE_URL=postgresql+psycopg://nutrition:nutrition_dev@localhost:5432/nutrition_test pytest
```

The Postgres suite upgrades, seeds twice, compares Alembic history to SQLAlchemy metadata, downgrades and re-upgrades, then exercises registration, login, and current-user authorization. It uses `nutrition_test` so it does not wipe local development data.

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

## Configuration

Configuration is loaded from environment variables. `.env.example` contains development-safe defaults; copy it to `.env` and replace `JWT_SECRET_KEY` before any shared or deployed environment. Never commit `.env` or production secrets.

## Project status

See [task_plan.md](task_plan.md) for the live implementation checklist and [PLAN.md](PLAN.md) for architecture, API, persistence, and phased delivery decisions.
