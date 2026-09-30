"""Dependency-free regression checks for the SEC-005 schema guardrails."""
from __future__ import annotations
from pathlib import Path
import unittest

MIGRATION = Path(__file__).resolve().parents[1] / "versions" / "0001_realtime_event_ledger.py"


class InitialLedgerSchemaContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.schema = MIGRATION.read_text(encoding="utf-8")

    def test_has_tournament_scoped_ordered_events(self) -> None:
        self.assertIn("CREATE TABLE official_game_events", self.schema)
        self.assertIn("UNIQUE (tournament_id, sequence)", self.schema)

    def test_has_single_transition_per_version(self) -> None:
        self.assertIn("resulting_state_version = expected_state_version + 1", self.schema)
        self.assertIn("UNIQUE (tournament_id, resulting_state_version)", self.schema)

    def test_has_scoped_idempotency_with_fingerprint(self) -> None:
        self.assertIn("request_fingerprint", self.schema)
        self.assertIn("UNIQUE (tournament_id, actor_subject_id, operation, idempotency_key)", self.schema)

    def test_transition_command_cannot_cross_tournament_boundary(self) -> None:
        self.assertIn("official_transitions_command_same_tournament_fk", self.schema)
        self.assertIn("REFERENCES idempotency_commands (tournament_id, id)", self.schema)

    def test_has_server_delivery_outbox(self) -> None:
        self.assertIn("CREATE TABLE realtime_outbox", self.schema)
        self.assertIn("realtime_outbox_event_same_tournament_fk", self.schema)

    def test_event_and_outbox_cannot_cross_tournament_boundary(self) -> None:
        self.assertIn("official_game_events_transition_same_tournament_fk", self.schema)
        self.assertIn("REFERENCES official_transitions (tournament_id, id)", self.schema)
        self.assertIn("REFERENCES official_game_events (tournament_id, id)", self.schema)

    def test_downgrade_is_dependency_ordered(self) -> None:
        self.assertLess(self.schema.index("DROP TABLE realtime_outbox"), self.schema.index("DROP TABLE official_game_events"))


if __name__ == "__main__":
    unittest.main()
