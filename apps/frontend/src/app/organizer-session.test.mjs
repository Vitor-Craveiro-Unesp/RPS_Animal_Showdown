import assert from "node:assert/strict";
import test from "node:test";
import { restoreTournamentSession, saveOrganizerSession, saveParticipantSession, saveTournamentView } from "./organizer-session.mjs";

function storage() {
  const values = new Map();
  return {
    getItem: (key) => values.get(key) ?? null,
    setItem: (key, value) => values.set(key, String(value)),
    removeItem: (key) => values.delete(key),
  };
}

test("organizer capability survives a normal refresh in the same browser tab", () => {
  const session = storage();
  saveOrganizerSession(session, { code: "RPS-PUBLIC-CODE", tournamentId: "tournament-a", organizerToken: "secret-organizer-capability" });
  saveTournamentView(session, { screen: "organizer", code: "RPS-PUBLIC-CODE", tournamentId: "tournament-a" });

  assert.deepEqual(restoreTournamentSession(session), {
    screen: "organizer", code: "RPS-PUBLIC-CODE", tournamentId: "tournament-a",
    organizerToken: "secret-organizer-capability", playerToken: "",
  });
});

test("participant persistence never retains the organizer capability", () => {
  const session = storage();
  saveOrganizerSession(session, { code: "RPS-A", tournamentId: "a", organizerToken: "organizer-secret" });
  saveParticipantSession(session, { code: "RPS-B", tournamentId: "b", playerToken: "participant-secret" });

  const restored = restoreTournamentSession(session);
  assert.equal(restored.organizerToken, "");
  assert.equal(restored.playerToken, "participant-secret");
});
