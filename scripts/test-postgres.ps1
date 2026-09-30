[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"

if ([string]::IsNullOrWhiteSpace($env:RPS_TEST_DATABASE_URL)) {
    throw "Set RPS_TEST_DATABASE_URL to an isolated PostgreSQL database URL before running this script."
}

if (-not $env:RPS_TEST_DATABASE_URL.StartsWith("postgresql://", [System.StringComparison]::OrdinalIgnoreCase)) {
    throw "RPS_TEST_DATABASE_URL must use the libpq postgresql:// form; the test derives DATABASE_URL for Alembic."
}

python -m pytest -q database/migrations/tests/test_postgres_constraints.py
