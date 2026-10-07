import assert from "node:assert/strict";
import test from "node:test";
import { hasCurrentTournamentArena, restoreTournamentSession, saveOrganizerSession, saveParticipantSession, saveTournamentView } from "./organizer-session.mjs";

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

test("a newly created tournament replaces the old organizer room and replay cache", () => {
  const session = storage();
  saveOrganizerSession(session, { code: "RPS-OLD", tournamentId: "old-id", organizerToken: "old-capability" });
  saveTournamentView(session, { screen: "arena", code: "RPS-OLD", tournamentId: "old-id" });
  session.setItem("rps-realtime-sequence:old-id", "42");
  session.setItem("rps-realtime-events:old-id", "[{}]");

  saveOrganizerSession(session, {
    code: "RPS-NEW", tournamentId: "new-id", organizerToken: "new-capability", previousTournamentId: "old-id",
  });
  saveTournamentView(session, { screen: "organizer", code: "RPS-NEW", tournamentId: "new-id" });

  assert.deepEqual(restoreTournamentSession(session), {
    screen: "organizer", code: "RPS-NEW", tournamentId: "new-id",
    organizerToken: "new-capability", playerToken: "",
  });
  assert.equal(session.getItem("rps-realtime-sequence:old-id"), null);
  assert.equal(session.getItem("rps-realtime-events:old-id"), null);
});

test("a finished arena from an old tournament cannot unlock the new organizer panel", () => {
  const oldArena = { tournament_id: "old-id", status: "completed" };
  assert.equal(hasCurrentTournamentArena(oldArena, "new-id"), false);
  assert.equal(hasCurrentTournamentArena(null, "new-id"), false);
  assert.equal(hasCurrentTournamentArena({ tournament_id: "new-id", status: "running" }, "new-id"), true);
});
