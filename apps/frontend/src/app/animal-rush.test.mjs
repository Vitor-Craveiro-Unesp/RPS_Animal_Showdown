import assert from "node:assert/strict";
import test from "node:test";

import {
  animalRushRoundDuration,
  randomAnimalRushMove,
  resolveAnimalRushAnswer,
  winningAnimalRushMove,
} from "./animal-rush.mjs";

test("each Animal Rush prompt requires the move that defeats it", () => {
  assert.equal(winningAnimalRushMove("rock"), "paper");
  assert.equal(winningAnimalRushMove("paper"), "scissors");
  assert.equal(winningAnimalRushMove("scissors"), "rock");
});

test("correct answers increase score and streak and preserve the session best", () => {
  assert.deepEqual(
    resolveAnimalRushAnswer("rock", "paper", { score: 8, streak: 4, bestStreak: 7 }),
    { score: 9, streak: 5, bestStreak: 7, correct: true },
  );
  assert.deepEqual(
    resolveAnimalRushAnswer("paper", "scissors", { score: 9, streak: 7, bestStreak: 7 }),
    { score: 10, streak: 8, bestStreak: 8, correct: true },
  );
});

test("an incorrect answer ends only the current streak", () => {
  assert.deepEqual(
    resolveAnimalRushAnswer("scissors", "scissors", { score: 12, streak: 6, bestStreak: 9 }),
    { score: 12, streak: 0, bestStreak: 9, correct: false },
  );
});

test("difficulty accelerates progressively and keeps a playable floor", () => {
  assert.equal(animalRushRoundDuration(0), 3_600);
  assert.equal(animalRushRoundDuration(2), 3_600);
  assert.equal(animalRushRoundDuration(3), 3_400);
  assert.ok(animalRushRoundDuration(12) < animalRushRoundDuration(6));
  assert.equal(animalRushRoundDuration(10_000), 1_200);
});

test("prompt selection covers deterministic random boundaries", () => {
  assert.equal(randomAnimalRushMove(() => 0), "rock");
  assert.equal(randomAnimalRushMove(() => 0.34), "paper");
  assert.equal(randomAnimalRushMove(() => 0.99), "scissors");
});
