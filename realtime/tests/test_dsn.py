from __future__ import annotations

import unittest

from realtime.dsn import to_psycopg_dsn, to_sqlalchemy_url


class DatabaseUrlTests(unittest.TestCase):
    def test_converts_between_sqlalchemy_and_psycopg_forms(self) -> None:
        sqlalchemy_url = "postgresql+psycopg://rps:password@localhost:5432/rps_test?sslmode=disable"
        psycopg_url = "postgresql://rps:password@localhost:5432/rps_test?sslmode=disable"
        self.assertEqual(to_psycopg_dsn(sqlalchemy_url), psycopg_url)
        self.assertEqual(to_sqlalchemy_url(psycopg_url), sqlalchemy_url)

    def test_rejects_unrelated_database_urls(self) -> None:
        with self.assertRaises(ValueError):
            to_psycopg_dsn("sqlite:///local.db")
        with self.assertRaises(ValueError):
            to_sqlalchemy_url("postgres://rps:password@localhost/rps_test")


if __name__ == "__main__":
    unittest.main()
