# Deployment guide

## Production topology

Run the API, Celery worker, Celery Beat, PostgreSQL, Redis, and static frontend as separate services. PostgreSQL is the durable source of truth. Redis is queue infrastructure and does not require durable application data in V1.

The included production Compose override is suitable for a single-host deployment and as a reference for managed container platforms. For larger deployments, use managed PostgreSQL and Redis, run exactly one Beat instance, and scale API and worker services independently.

## Required configuration

Set these values outside source control:

- `ENVIRONMENT=production`
- `DATABASE_URL` using the `postgresql+psycopg://` driver
- `REDIS_URL`, `CELERY_BROKER_URL`, and `CELERY_RESULT_BACKEND`
- `JWT_SECRET_KEY`, generated randomly with at least 32 characters
- `FRONTEND_ORIGIN`, the exact public browser origin
- `VITE_API_URL`, the public API URL embedded into the frontend build

Use TLS for public traffic and database connections whenever the provider supports it. Restrict PostgreSQL and Redis to private networking and do not publish their ports publicly.

## Single-host deployment

Create `.env` from `.env.example`, replace every development credential, and set the two public URLs. Then build and start:

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build
docker compose -f docker-compose.yml -f docker-compose.prod.yml ps
```

The production backend command applies Alembic migrations before starting API workers. The Celery services wait for the API health check, ensuring schema upgrades finish first. Back up PostgreSQL before each deployment that includes migrations.

## Verification and rollback

Verify both health endpoints after deployment:

```bash
curl --fail https://api.example.com/health
curl --fail https://app.example.com/health
```

Also complete one register/login request and inspect worker/Beat logs. For rollback, deploy the previous image tag. Do not automatically downgrade the database; review the migration and restore the pre-deployment backup when a schema rollback is required.

## Release gate

Every pull request and push to `main` runs backend lint and tests against PostgreSQL, frontend lint/tests/build, Compose validation, and container builds. Run the equivalent checks locally before release:

```bash
cd backend && ruff check . && pytest
cd ../frontend && npm run lint && npm test && npm run build
cd .. && docker compose config --quiet && docker compose build backend frontend
```
