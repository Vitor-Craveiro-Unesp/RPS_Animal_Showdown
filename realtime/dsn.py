"""Explicit PostgreSQL DSN adapters for the two database client APIs.

Alembic/SQLAlchemy requires a dialect-qualified URL.  psycopg speaks the
PostgreSQL/libpq form directly.  Keeping the conversion here prevents a
SQLAlchemy URL leaking into ``psycopg.connect`` at a runtime boundary.
"""
from __future__ import annotations


SQLALCHEMY_PREFIX = "postgresql+psycopg://"
PSYCOPG_PREFIX = "postgresql://"


def to_psycopg_dsn(database_url: str) -> str:
    """Return a libpq-compatible URL accepted by ``psycopg.connect``."""
    if database_url.startswith(SQLALCHEMY_PREFIX):
        return PSYCOPG_PREFIX + database_url[len(SQLALCHEMY_PREFIX) :]
    if database_url.startswith(PSYCOPG_PREFIX):
        return database_url
    raise ValueError("database URL must start with postgresql:// or postgresql+psycopg://")


def to_sqlalchemy_url(database_url: str) -> str:
    """Return the SQLAlchemy URL used only by Alembic/SQLAlchemy."""
    if database_url.startswith(SQLALCHEMY_PREFIX):
        return database_url
    if database_url.startswith(PSYCOPG_PREFIX):
        return SQLALCHEMY_PREFIX + database_url[len(PSYCOPG_PREFIX) :]
    raise ValueError("database URL must start with postgresql:// or postgresql+psycopg://")
