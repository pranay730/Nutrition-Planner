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

## Phase 2: persistence

- [x] Define normalized SQLAlchemy domain models and constraints.
- [x] Configure Alembic and generate the baseline migration.
- [x] Add canonical cuisine-tagged ingredients and recipes.
- [x] Add an idempotent seed command.
- [x] Add persistence and seed tests.
- [x] Verify upgrade, seed, idempotent reseed, downgrade, and re-upgrade on PostgreSQL.
- [x] Automate seed integrity, reseed updates, unique/check constraints, and foreign keys.
- [x] Automate Postgres migrate, seed-twice, metadata parity, downgrade, and re-upgrade.
- [x] Run the complete Phase 2 quality gate.

## Phase 3: authentication and authorization (current request)

- [x] Add Argon2id password hashing and hash-upgrade support.
- [x] Add issuer-, audience-, and expiry-validated JWT access tokens.
- [x] Add user repository and authentication service layers.
- [x] Implement `POST /auth/register` and `POST /auth/login`.
- [x] Implement protected `GET /users/me`.
- [x] Prevent client-selected ownership by deriving the current user from the token.
- [x] Add registration, login, invalid credential, token, and authorization tests.
- [x] Verify the authentication flow against containerized PostgreSQL.
- [x] Run the complete Phase 3 quality gate.

## Future phases (not started)

- [ ] Implement onboarding and calorie calculation.
- [ ] Implement cuisine preferences and pantry suggestions.
- [ ] Implement schedules and pantry management.
- [ ] Implement meal logging and daily-plan allocation.
- [ ] Implement deterministic recommendation engine.
- [ ] Implement reminder and notification workflow.
- [ ] Build the React product screens.
- [ ] Complete backend/frontend test suites and deployment hardening.
