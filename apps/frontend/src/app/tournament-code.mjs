// Use the same public-code normalization as the backend before constructing
// follow-up URLs. A successful join can otherwise be followed by a 404 when
// the pasted code has leading or trailing whitespace.
export function normalizeTournamentCode(code) {
  return code.trim().toUpperCase();
}

export function tournamentApiPath(code, endpoint) {
  return `/api/v1/tournaments/${encodeURIComponent(normalizeTournamentCode(code))}/${endpoint}`;
}
