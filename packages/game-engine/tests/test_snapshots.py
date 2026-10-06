from __future__ import annotations

import json
import unittest
from copy import deepcopy
from dataclasses import replace

from rps_game_engine import (
    ALL_STRATEGY_CONDITIONS,
    Competitor,
    EngineValidationError,
    Move,
    StrategyCondition,
    play_training_round,
    play_active_match_round,
    start_training,
    start_tournament,
    strategy_from_payload,
    strategy_to_payload,
    tournament_state_from_snapshot,
    tournament_state_to_snapshot,
)

from .helpers import ConstantRandom, distribution_for, strategy_for


TOURNAMENT_ID = "00000000-0000-4000-8000-000000000001"
PLAYER_ONE_ID = "00000000-0000-4000-8000-000000000101"
PLAYER_TWO_ID = "00000000-0000-4000-8000-000000000102"
PLAYER_THREE_ID = "00000000-0000-4000-8000-000000000103"


class StrategyPayloadTests(unittest.TestCase):
    def test_round_trip_uses_all_canonical_conditions(self) -> None:
        strategy = strategy_for(
            Move.ROCK,
            {StrategyCondition.TIED_WITH_PAPER: Move.SCISSORS},
        )

        payload = strategy_to_payload(strategy)
        restored = strategy_from_payload(json.loads(json.dumps(payload)))

        self.assertEqual(set(payload), {condition.value for condition in ALL_STRATEGY_CONDITIONS})
        self.assertEqual(restored, strategy)
        self.assertEqual(payload["tied_with_paper"], {"rock": 0, "paper": 0, "scissors": 100})

    def test_rejects_legacy_tied_on_alias_and_extra_distribution_fields(self) -> None:
        payload = strategy_to_payload(strategy_for(Move.ROCK))
        payload["tied_on_rock"] = payload.pop("tied_with_rock")
        with self.assertRaises(EngineValidationError) as alias:
            strategy_from_payload(payload)
        self.assertEqual(alias.exception.code, "snapshot.invalid_fields")

        payload = strategy_to_payload(strategy_for(Move.ROCK))
        payload["initial"]["winner"] = 1
        with self.assertRaises(EngineValidationError) as forged:
            strategy_from_payload(payload)
        self.assertEqual(forged.exception.code, "snapshot.invalid_fields")

    def test_copies_payload_into_an_immutable_strategy(self) -> None:
        payload = strategy_to_payload(strategy_for(Move.ROCK))
        restored = strategy_from_payload(payload)
        payload["initial"]["rock"] = 0
        payload["initial"]["paper"] = 100

        self.assertEqual(restored.for_condition(StrategyCondition.INITIAL), distribution_for(Move.ROCK))


class TournamentSnapshotTests(unittest.TestCase):
    def _state(self):
        return start_tournament(
            TOURNAMENT_ID,
            (
                Competitor(PLAYER_ONE_ID, strategy_for(Move.ROCK)),
                Competitor(PLAYER_TWO_ID, strategy_for(Move.SCISSORS)),
                Competitor(PLAYER_THREE_ID, strategy_for(Move.PAPER)),
            ),
            2,
            ConstantRandom(),
        )

    def test_active_state_round_trip_is_json_compatible_and_equal(self) -> None:
        original = play_active_match_round(self._state(), ConstantRandom()).state

        snapshot = tournament_state_to_snapshot(original)
        persisted_bytes = json.dumps(
            snapshot,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        loaded_snapshot = json.loads(persisted_bytes.decode("utf-8"))
        restored = tournament_state_from_snapshot(loaded_snapshot)

        self.assertEqual(snapshot["schema_version"], 3)
        self.assertEqual(snapshot["kind"], "tournament_state")
        self.assertEqual(restored, original)
        self.assertIsNot(restored, original)
        self.assertIsNot(restored.competitors[0].strategy, original.competitors[0].strategy)
        self.assertEqual(
            play_active_match_round(restored, ConstantRandom()).state,
            play_active_match_round(original, ConstantRandom()).state,
        )

    def test_loaded_snapshot_is_copied_and_keeps_official_strategy_frozen(self) -> None:
        snapshot = tournament_state_to_snapshot(self._state())
        loaded_snapshot = json.loads(json.dumps(snapshot))
        restored = tournament_state_from_snapshot(loaded_snapshot)

        loaded_snapshot["competitors"][0]["strategy"]["initial"] = {  # type: ignore[index]
            "rock": 0,
            "paper": 100,
            "scissors": 0,
        }
        self.assertEqual(
            restored.competitors[0].strategy.for_condition(StrategyCondition.INITIAL),
            distribution_for(Move.ROCK),
        )

    def test_training_from_a_restored_competitor_cannot_change_official_state(self) -> None:
        original = self._state()
        restored = tournament_state_from_snapshot(
            json.loads(json.dumps(tournament_state_to_snapshot(original)))
        )
        training = start_training("training-only", restored.competitors[0], 2)

        trained = play_training_round(training, Move.PAPER, ConstantRandom()).state

        self.assertEqual(original, restored)
        self.assertEqual(restored.competitors[0].strategy, original.competitors[0].strategy)
        self.assertEqual(restored.current_round, original.current_round)
        self.assertEqual(trained.character_hearts, 1)

    def test_rejects_generic_dataclass_dump_instead_of_canonical_adapter_snapshot(self) -> None:
        canonical = tournament_state_to_snapshot(self._state())
        generic_dump = deepcopy(canonical)
        generic_dump.pop("schema_version")
        generic_dump.pop("kind")
        for competitor in generic_dump["competitors"]:  # type: ignore[union-attr]
            competitor["strategy"] = {"distributions": competitor["strategy"]}

        with self.assertRaises(EngineValidationError) as raised:
            tournament_state_from_snapshot(generic_dump)
        self.assertEqual(raised.exception.code, "snapshot.invalid_fields")

    def test_completed_state_round_trip_preserves_bracket_history(self) -> None:
        state = self._state()
        while state.champion_id is None:
            state = play_active_match_round(state, ConstantRandom()).state

        restored = tournament_state_from_snapshot(
            json.loads(json.dumps(tournament_state_to_snapshot(state)))
        )

        self.assertEqual(restored, state)
        self.assertEqual(len(restored.completed_rounds), 2)
        self.assertEqual(restored.champion_id, PLAYER_TWO_ID)

    def test_reconstruction_deep_validates_forged_official_state(self) -> None:
        state = play_active_match_round(self._state(), ConstantRandom()).state
        snapshot = tournament_state_to_snapshot(state)
        assert snapshot["current_round"] is not None
        current_round = snapshot["current_round"]
        assert isinstance(current_round, dict)
        battle = current_round["matches"][0]["battle"]  # type: ignore[index]
        battle["player_two_hearts"] = 2

        with self.assertRaises(EngineValidationError) as raised:
            tournament_state_from_snapshot(snapshot)
        self.assertEqual(raised.exception.code, "match.state_hearts_mismatch")

    def test_rejects_wrong_kind_version_and_unknown_fields(self) -> None:
        valid = tournament_state_to_snapshot(self._state())
        cases = (
            ("kind", "training_state", "snapshot.invalid_kind"),
            ("schema_version", 999, "snapshot.unsupported_version"),
        )
        for field, value, code in cases:
            payload = deepcopy(valid)
            payload[field] = value
            with self.subTest(field=field), self.assertRaises(EngineValidationError) as raised:
                tournament_state_from_snapshot(payload)
            self.assertEqual(raised.exception.code, code)

        payload = deepcopy(valid)
        payload["client_winner"] = PLAYER_ONE_ID
        with self.assertRaises(EngineValidationError) as raised:
            tournament_state_from_snapshot(payload)
        self.assertEqual(raised.exception.code, "snapshot.invalid_fields")

    def test_requires_canonical_uuid_identifiers_at_persistence_boundary(self) -> None:
        noncanonical = start_tournament(
            TOURNAMENT_ID.replace("-", ""),
            (
                Competitor(PLAYER_ONE_ID, strategy_for(Move.ROCK)),
                Competitor(PLAYER_TWO_ID, strategy_for(Move.SCISSORS)),
            ),
            1,
            ConstantRandom(),
        )
        with self.assertRaises(EngineValidationError) as serialization:
            tournament_state_to_snapshot(noncanonical)
        self.assertEqual(serialization.exception.code, "snapshot.noncanonical_uuid")

        payload = tournament_state_to_snapshot(self._state())
        payload["competitors"][0]["player_id"] = "not-a-uuid"  # type: ignore[index]
        with self.assertRaises(EngineValidationError) as restoration:
            tournament_state_from_snapshot(payload)
        self.assertEqual(restoration.exception.code, "snapshot.invalid_uuid")

    def test_rejects_non_integer_values_including_boolean(self) -> None:
        payload = tournament_state_to_snapshot(self._state())
        payload["hearts_per_match"] = True
        with self.assertRaises(EngineValidationError) as raised:
            tournament_state_from_snapshot(payload)
        self.assertEqual(raised.exception.code, "snapshot.invalid_integer")

    def test_rejects_duplicate_match_ids_across_bracket_rounds(self) -> None:
        state = self._state()
        for _ in range(4):
            state = play_active_match_round(state, ConstantRandom()).state
        self.assertTrue(state.completed_rounds)
        self.assertIsNotNone(state.current_round)
        assert state.current_round is not None

        duplicate_id = state.completed_rounds[0].matches[0].match_id
        current_match = state.current_round.matches[0]
        duplicate_match = replace(
            current_match,
            match_id=duplicate_id,
            battle=replace(current_match.battle, match_id=duplicate_id),
        )
        forged = replace(
            state,
            current_round=replace(state.current_round, matches=(duplicate_match,)),
        )

        with self.assertRaises(EngineValidationError) as raised:
            tournament_state_to_snapshot(forged)
        self.assertEqual(raised.exception.code, "tournament.invalid_match_id")


if __name__ == "__main__":
    unittest.main()
