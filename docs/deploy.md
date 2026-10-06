# Development and deployment baseline

For the Round 8.1 production handoff, environment matrix, Render blueprint and
the safe deployment order, see [production readiness](deployment/production-readiness.md).

## Local development

1. Copy `.env.example` to `.env` and use only local values.
2. Run `docker compose up --build` from the repository root.
3. Frontend is available at `http://localhost:3000`; the backend health endpoint is `http://localhost:8000/health`.

The Compose stack is intentionally limited to frontend, backend and PostgreSQL. It is a development baseline, not a production deployment manifest.

## CI and dependency reproducibility

The GitHub Actions workflow uses explicit `contents: read` permissions, immutable action commit SHAs and `persist-credentials: false` for checkouts. It runs on `pull_request` and pushes to `main`, does not use `pull_request_target`, and does not reference repository or deployment secrets. Pull-request code therefore receives no configured secret values.

Frontend dependencies are locked in the versioned root `package-lock.json`. CI and the frontend Docker image use `npm ci`; do not replace it with `npm install`. The CI executes `npm audit --omit=dev --audit-level=high`, so production dependency vulnerabilities at high or critical severity fail the check. The backend job runs `pip-audit` against its runtime requirements.

The frontend uses Next.js 16.3.7 and requires Node.js 20.9 or later; CI pins Node 20.19.0. This upgrade removes the high-severity PostCSS advisory that could not be corrected on the Next.js 15 release line. Validate upgrades with `npm ci`, `npm audit --omit=dev --audit-level=high`, `npm run lint:frontend` and `npm run build:frontend`.

The Python CI job starts an isolated PostgreSQL 16 service and sets `RPS_TEST_DATABASE_URL` only in libpq form (`postgresql://…`), because this is the value passed to `psycopg.connect()`. The PostgreSQL integration test derives a process-local `DATABASE_URL` in SQLAlchemy form (`postgresql+psycopg://…`) exclusively for Alembic, applies the migrations, and proves constraints, ordered replay and concurrent outbox claims against the running service. CI then executes backend, Game Engine, realtime and migration suites. The service credentials are non-secret, CI-only values and must never be reused outside this ephemeral test database. Migrations remain an explicit deployment action; neither Compose nor the application container applies them automatically.

## PostgreSQL integration validation

The database integration check is intentionally opt-in locally: it never creates
a database or falls back to a development database. Point
`RPS_TEST_DATABASE_URL` at an isolated disposable PostgreSQL database using the
libpq `postgresql://…` form, then run the script:

```powershell
$env:RPS_TEST_DATABASE_URL = "postgresql://rps_test:local-development-only@localhost:5432/rps_animal_showdown_test"
.\scripts\test-postgres.ps1
```

The Compose PostgreSQL service binds only `127.0.0.1:55432`. Do not reuse its
development database for this host-run test: run it against a separate local
PostgreSQL 16 database or a disposable CI database instead. If Docker is
unavailable, that same existing local instance or CI database is the supported
path; this does not change the application architecture or bypass the
PostgreSQL checks.

## Container execution

The frontend image installs dependencies as the unprivileged `node` user and copies application files with `node:node` ownership. The backend image installs the Game Engine package before switching to the unprivileged `app` user, so the production container can import the same Engine used by the HTTP boundary. Both conditions should be preserved when Dockerfiles change.

Before changing frontend dependencies, run `npm install` at the repository root to intentionally update `package-lock.json`, then validate with `npm ci`, lint, build and the audit command. No dependency scan result should be waived for a public release without an explicit Security review.

`REALTIME_TICKET_SIGNING_KEY` is required whenever the Backend has a
`DATABASE_URL` and enables its durable PostgreSQL/realtime path. Compose fails
before startup when the variable is absent. The committed `.env.example`
contains a development-only placeholder with the required minimum length;
replace it with an independently generated secret in every deployed
environment, stored only in that environment's secret manager. The CI value is
ephemeral and is never a production credential.

## Deferred deployment choices

The core suggests Vercel and Supabase, but hosting, managed database, realtime provider, production domains, TLS, backups, monitoring, secret storage and CI/CD release credentials need an explicit DevOps and Security decision. No production credentials belong in this repository.
