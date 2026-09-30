"""Regression checks for persisted access and reconstructible state schemas."""
from __future__ import annotations

from pathlib import Path
import unittest

MIGRATION = Path(__file__).resolve().parents[1] / "versions" / "0002_authoritative_snapshots_and_access.py"


class AuthoritativeSnapshotsSchemaContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.schema = MIGRATION.read_text(encoding="utf-8")

    def test_persists_revocable_capabilities_and_tickets_scoped_by_uuid(self) -> None:
        self.assertIn("CREATE TABLE tournament_access_capabilities", self.schema)
        self.assertIn("secret_hash", self.schema)
        self.assertIn("revoked_at", self.schema)
        self.assertIn("CREATE TABLE realtime_access_tickets", self.schema)
        self.assertIn("realtime_access_tickets_capability_same_tournament_fk", self.schema)
        self.assertIn("REFERENCES tournament_access_capabilities (tournament_id, id)", self.schema)

    def test_persists_frozen_strategy_and_engine_state_snapshots(self) -> None:
        for table in ("player_strategies", "official_player_snapshots", "official_matches", "official_match_rounds", "official_state_snapshots"):
            self.assertIn(f"CREATE TABLE {table}", self.schema)
        self.assertIn("strategy_document JSONB NOT NULL", self.schema)
        self.assertIn("state_document JSONB NOT NULL", self.schema)
        self.assertIn("official_state_snapshots_digest_same_tournament_fk", self.schema)
        self.assertIn("REFERENCES official_transitions (tournament_id, resulting_state_version, state_digest)", self.schema)

    def test_snapshot_relations_use_tournament_scoped_foreign_keys(self) -> None:
        self.assertIn("REFERENCES tournament_members (tournament_id, id)", self.schema)
        self.assertIn("REFERENCES player_strategies (tournament_id, id)", self.schema)
        self.assertIn("REFERENCES official_player_snapshots (tournament_id, id)", self.schema)
        self.assertIn("REFERENCES official_matches (tournament_id, id)", self.schema)


class TicketGrantIntegritySchemaContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        migration = Path(__file__).resolve().parents[1] / "versions" / "0003_ticket_grant_integrity.py"
        cls.schema = migration.read_text(encoding="utf-8")

    def test_ticket_must_match_capability_subject_role_and_tournament(self) -> None:
        self.assertIn("tournament_access_capabilities_grant_unique", self.schema)
        self.assertIn("realtime_access_tickets_capability_grant_same_tournament_fk", self.schema)
        self.assertIn("FOREIGN KEY (tournament_id, capability_id, subject_id, role)", self.schema)
        self.assertIn("REFERENCES tournament_access_capabilities (tournament_id, id, subject_id, role)", self.schema)


if __name__ == "__main__":
    unittest.main()
