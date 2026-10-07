import assert from "node:assert/strict";
import test from "node:test";
import { normalizeTournamentCode, tournamentApiPath } from "./tournament-code.mjs";

test("a pasted code with spaces uses the same canonical room for joining and strategy", () => {
  const pasted = "  rps-txkhtny759248ahl  ";
  assert.equal(normalizeTournamentCode(pasted), "RPS-TXKHTNY759248AHL");
  assert.equal(tournamentApiPath(pasted, "players/me/strategy"),
    "/api/v1/tournaments/RPS-TXKHTNY759248AHL/players/me/strategy");
  assert.equal(tournamentApiPath(pasted, "players/me/ready"),
    "/api/v1/tournaments/RPS-TXKHTNY759248AHL/players/me/ready");
});
