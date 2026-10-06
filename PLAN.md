# Nutrition Planner V1 Implementation Plan

## V1 architecture

The application is a modular monolith: one React client, one FastAPI application, one PostgreSQL database, and one Celery worker backed by Redis. PostgreSQL is the source of truth. Redis is limited to Celery queue/result transport in V1. HTTP handlers validate and translate requests, services own business rules, and repositories own SQLAlchemy queries.

```text
React/Vite -> FastAPI routers -> services -> repositories -> PostgreSQL
                                      |
                                      +-> Celery tasks -> Redis broker
```

Cheap state calculations (meal totals, remaining calories, and recommendations) remain synchronous. Celery is used only for meal reminders and future notification delivery adapters.

## Folder structure

```text
backend/
  alembic/                 database migrations
  app/
    api/                   HTTP routers and dependencies
    auth/                  authentication domain
    core/                  settings, database, security, Celery
    meals/                 meal logging domain
    models/                SQLAlchemy models
    notifications/         notification records and delivery boundary
    onboarding/            profile and preference workflow
    pantry/                ingredients and pantry domain
    recommendations/       deterministic scoring engine
    repositories/          shared data-access abstractions when warranted
    schedules/             meal schedules and reminder tasks
    schemas/               shared Pydantic schemas
    services/              cross-domain orchestration such as daily planning
    users/                  user domain
    main.py                 application factory/entry point
  tests/
frontend/
  src/
    api/                    typed backend client
    components/             reusable UI
    features/               auth, onboarding, dashboard, meals, pantry
    pages/                  route-level screens
    test/                   test setup
```

Domain packages will gain router, schema, service, and repository modules only when needed; empty abstractions are avoided.

## Database entities

- `users`: email identity, password hash, timestamps.
- `profiles`: one-to-one health/goal inputs and calculated daily calorie target.
- `cuisine_preferences`: normalized many-per-user cuisine selections.
- `meal_schedules`: meal type and preferred local time per user.
- `ingredients`: canonical ingredient catalog with category.
- `ingredient_cuisine_tags`: many-to-many ingredient/cuisine mapping for suggestions.
- `pantry_items`: per-user ingredient status (`available`, `low`, `unavailable`).
- `recipes`: internal meal metadata and nutrition totals.
- `recipe_ingredients`: normalized recipe ingredient membership.
- `meal_logs`: user-entered meals, calories, name/notes, and timestamp.
- `notifications`: generated reminder content and read/delivery state.

Recommendation history will not be persisted initially: recommendations are derived from current state. `remaining_calories` is also derived from the daily target minus today's meal logs.

## API endpoints

- `GET /health`
- `POST /auth/register`, `POST /auth/login`
- `GET /users/me`
- `PUT /onboarding/profile`
- `PUT /preferences/cuisines`
- `GET /ingredients/suggestions`
- `PUT /meal-schedules`
- `GET /pantry`, `PUT /pantry`, `PUT /pantry/{ingredient_id}`
- `POST /meals`, `GET /meals/today`
- `GET /daily-plan`
- `GET /recommendations/next`
- `GET /notifications`, `PATCH /notifications/{notification_id}`

User-specific routes require a JWT and derive the user ID from the token, never from a client-supplied ownership field.

## Implementation phases

1. Foundation: monorepo, configuration, Docker Compose, FastAPI health endpoint, PostgreSQL/Redis clients, smoke test.
2. Persistence: SQLAlchemy models, Alembic baseline migration, recipe/ingredient seed tooling.
3. Authentication: Argon2 password hashing, JWT access tokens, current-user dependency, authorization tests.
4. Onboarding: profile validation/calorie service, cuisine preferences, schedules, adaptive pantry suggestions.
5. Daily state: meal logging, timezone-aware daily totals, remaining-meal allocation service.
6. Recommendations: deterministic weighted scoring, explanations, isolated unit tests.
7. Reminders: Celery scheduling, notification records, idempotent reminder tasks.
8. Frontend: auth, two-minute onboarding, dashboard, meal logging, pantry management.
9. Hardening: integration tests, lint/type checks, container health checks, deployment documentation.

Each phase must pass its relevant tests before the next phase begins.

## Major design decisions

- **SQLAlchemy 2 synchronous sessions:** the application workload is conventional CRUD and Celery is synchronous. This keeps transaction handling and worker reuse simple; FastAPI runs sync dependencies in its thread pool.
- **Pydantic Settings:** environment variables are validated once and shared by API and worker processes.
- **App factory:** tests can construct the application without requiring live PostgreSQL or Redis connections. Infrastructure clients are lazy, while container health checks verify live services.
- **No stored derived daily plan:** totals and recommendations are calculated from current source data to prevent drift.
- **Normalized cuisine tags and recipe ingredients:** supports deterministic matching without JSON-specific query logic or duplicated strings.
- **JWT access tokens only in the first auth slice:** refresh/revocation adds operational state and will be considered only if deployment requirements justify it.
- **Celery Beat for recurring schedule discovery:** a periodic dispatcher can find reminders due soon and enqueue idempotent tasks. This is simpler and more resilient to schedule edits than maintaining one long-lived task per schedule.
- **UTC persistence with a future user timezone field:** timestamps are stored in UTC; schedule evaluation converts through the user's timezone. The timezone field will be added with the profile/schedule model phase.
- **UUID application identifiers:** domain rows use UUIDs so identifiers remain safe to generate outside a single database process and do not expose row counts.
- **Portable string enums with database checks:** evolving V1 statuses remain readable strings and are constrained by PostgreSQL without creating PostgreSQL-native enum migration friction.
- **Idempotent canonical seed data:** ingredients and recipes are matched by unique names, updated in place, and have their normalized associations reconciled on every seed run.
- **Argon2id password hashing:** password verification uses a memory-hard hash and transparently upgrades stored hashes when parameters change.
- **Short-lived stateless access tokens:** JWTs contain only the user subject and standard access-token claims, are audience/issuer validated, and expire after 30 minutes by default. Refresh and revocation state remain outside V1 until deployment needs justify them.
- **Token-derived authorization:** protected handlers resolve the active user from the signed JWT subject and never accept a client-provided owner ID.
- **Server-calculated calorie targets:** onboarding uses Mifflin-St Jeor, explicit activity factors, and a conservative goal adjustment. Targets are rounded deterministically and bounded to the persistence safety range.
- **Replace-style onboarding collections:** cuisine preferences and meal schedules are submitted as complete sets, making retries idempotent and removal behavior unambiguous.
- **Preference-ranked pantry suggestions:** canonical ingredients matching more of the user's selected cuisines sort first, with ingredient name as the deterministic tie-breaker.
- **Timezone-bounded daily state:** daily meal queries convert the profile's local midnight boundaries to UTC before querying, so totals remain correct across offsets and daylight-saving transitions.
- **Derived exact meal allocation:** the daily plan reports the signed target-minus-consumed balance and distributes its positive portion across upcoming, unlogged schedule slots. Integer remainders are assigned in schedule order so allocations always sum exactly.
