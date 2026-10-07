// Browser-only persistence for opaque room capabilities.  Values are never
// placed in routes, rendered markup, analytics data, or participant payloads.
const keys = Object.freeze({
  screen: "rps-screen",
  code: "rps-code",
  tournamentId: "rps-tournament-id",
  organizer: "rps-organizer",
  player: "rps-player",
});

export function restoreTournamentSession(storage) {
  return {
    screen: storage.getItem(keys.screen) ?? "",
    code: storage.getItem(keys.code) ?? "",
    tournamentId: storage.getItem(keys.tournamentId) ?? "",
    organizerToken: storage.getItem(keys.organizer) ?? "",
    playerToken: storage.getItem(keys.player) ?? "",
  };
}

export function saveOrganizerSession(storage, { code, tournamentId, organizerToken, previousTournamentId = "" }) {
  if (previousTournamentId && previousTournamentId !== tournamentId) {
    storage.removeItem(`rps-realtime-sequence:${previousTournamentId}`);
    storage.removeItem(`rps-realtime-events:${previousTournamentId}`);
  }
  storage.setItem(keys.code, code);
  storage.setItem(keys.tournamentId, tournamentId);
  storage.setItem(keys.organizer, organizerToken);
  storage.removeItem(keys.player);
}

export function saveParticipantSession(storage, { code, tournamentId, playerToken }) {
  storage.setItem(keys.code, code);
  storage.setItem(keys.tournamentId, tournamentId);
  storage.setItem(keys.player, playerToken);
  storage.removeItem(keys.organizer);
}

export function saveTournamentView(storage, { screen, code, tournamentId }) {
  storage.setItem(keys.screen, screen);
  storage.setItem(keys.code, code);
  storage.setItem(keys.tournamentId, tournamentId);
}

export function hasCurrentTournamentArena(officialState, tournamentId) {
  return Boolean(tournamentId && officialState?.tournament_id === tournamentId);
}
