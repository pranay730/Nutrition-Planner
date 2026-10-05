# Nutrition Planner

A production-oriented modular monolith that recommends what a user should eat next based on their daily calorie budget, meal schedule, preferences, pantry, and meal history.

This repository currently contains the Phase 1 foundation: React/Vite, FastAPI, PostgreSQL, Redis, Celery, Docker Compose, and a health endpoint. Product features described in [PLAN.md](PLAN.md) are intentionally deferred until this foundation is verified.

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

## Frontend development without Docker

```bash
cd frontend
npm install
npm run dev
```

## Database migrations and seed data

Alembic migrations and the seed command are scheduled for Phase 2. They are listed here to keep the intended developer workflow explicit; commands will be added only after the first models exist.

## Configuration

Configuration is loaded from environment variables. `.env.example` contains development-safe defaults; copy it to `.env` and replace `JWT_SECRET_KEY` before any shared or deployed environment. Never commit `.env` or production secrets.

## Project status

See [task_plan.md](task_plan.md) for the live implementation checklist and [PLAN.md](PLAN.md) for architecture, API, persistence, and phased delivery decisions.
