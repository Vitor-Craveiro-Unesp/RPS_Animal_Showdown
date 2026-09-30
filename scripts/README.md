# Scripts

Scripts must document required environment variables and must not embed credentials.

## PostgreSQL integration check

`test-postgres.ps1` runs the migration/realtime integration suite against an
already provisioned, isolated database. Set `RPS_TEST_DATABASE_URL` to a libpq
`postgresql://…` URL first. The test derives the SQLAlchemy `DATABASE_URL`
needed by Alembic only for its subprocess.

```powershell
$env:RPS_TEST_DATABASE_URL = "postgresql://user:password@localhost:5432/rps_test"
.\scripts\test-postgres.ps1
```

It does not create databases. It applies migrations only to the database named
by this test-only variable, so it must never target a development, staging or
production database.
