# Codex Task Plan

Status legend: `[ ]` pending, `[~]` in progress, `[x]` complete.

## Phase 1: foundation

- [x] Inspect the repository and existing Git state.
- [x] Define V1 architecture and decisions in `PLAN.md`.
- [x] Create backend and frontend project structure.
- [x] Add FastAPI application and `/health` endpoint.
- [x] Configure SQLAlchemy/PostgreSQL connectivity.
- [x] Configure Redis and Celery connectivity.
- [x] Add Dockerfiles and Docker Compose services.
- [x] Add backend health endpoint test.
- [x] Add environment example and development README.
- [x] Run backend tests and fix failures.
- [x] Validate Docker Compose configuration.

## Phase 2: persistence (current request)

- [x] Define normalized SQLAlchemy domain models and constraints.
- [x] Configure Alembic and generate the baseline migration.
- [x] Add canonical cuisine-tagged ingredients and recipes.
- [x] Add an idempotent seed command.
- [x] Add persistence and seed tests.
- [x] Verify upgrade, seed, idempotent reseed, downgrade, and re-upgrade on PostgreSQL.
- [x] Run the complete Phase 2 quality gate.

## Future phases (not started)

- [ ] Implement authentication and authorization.
- [ ] Implement onboarding and calorie calculation.
- [ ] Implement cuisine preferences and pantry suggestions.
- [ ] Implement schedules and pantry management.
- [ ] Implement meal logging and daily-plan allocation.
- [ ] Implement deterministic recommendation engine.
- [ ] Implement reminder and notification workflow.
- [ ] Build the React product screens.
- [ ] Complete backend/frontend test suites and deployment hardening.
