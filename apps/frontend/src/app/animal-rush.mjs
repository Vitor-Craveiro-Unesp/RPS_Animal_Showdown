// @ts-check

/** @typedef {"rock" | "paper" | "scissors"} AnimalRushMove */

/** @type {readonly AnimalRushMove[]} */
export const ANIMAL_RUSH_MOVES = Object.freeze(["rock", "paper", "scissors"]);

/**
 * Return the only move that defeats the prompt according to standard RPS.
 * @param {AnimalRushMove} prompt
 * @returns {AnimalRushMove}
 */
export function winningAnimalRushMove(prompt) {
  if (prompt === "rock") return "paper";
  if (prompt === "paper") return "scissors";
  return "rock";
}

/**
 * Pick one prompt. The injectable source keeps this deterministic in tests.
 * @param {() => number} [randomSource]
 * @returns {AnimalRushMove}
 */
export function randomAnimalRushMove(randomSource = Math.random) {
  const index = Math.min(ANIMAL_RUSH_MOVES.length - 1, Math.floor(randomSource() * ANIMAL_RUSH_MOVES.length));
  return ANIMAL_RUSH_MOVES[Math.max(0, index)];
}

/**
 * Gentle, predictable difficulty curve: 3.6s initially, 200ms faster after
 * every three consecutive hits, with a 1.2s accessibility floor.
 * @param {number} streak
 */
export function animalRushRoundDuration(streak) {
  const safeStreak = Math.max(0, Math.floor(streak));
  return Math.max(1_200, 3_600 - Math.floor(safeStreak / 3) * 200);
}

/**
 * Resolve scoring without knowing anything about the tournament.
 * @param {AnimalRushMove} prompt
 * @param {AnimalRushMove} answer
 * @param {{score:number, streak:number, bestStreak:number}} state
 */
export function resolveAnimalRushAnswer(prompt, answer, state) {
  const correct = answer === winningAnimalRushMove(prompt);
  if (!correct) return { ...state, streak: 0, correct };
  const streak = state.streak + 1;
  return {
    score: state.score + 1,
    streak,
    bestStreak: Math.max(state.bestStreak, streak),
    correct,
  };
}
