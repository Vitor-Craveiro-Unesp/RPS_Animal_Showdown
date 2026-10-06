/**
 * The official snapshot is a server-authoritative synchronization path.  It
 * must remain distinguishable from a subscribed WebSocket, while avoiding a
 * misleading permanent "connecting" label when the current state is already
 * available to the organizer.
 */
export function realtimeDisplayStatus({ hasSnapshot, websocketSubscribed }) {
  if (websocketSubscribed) return "live";
  return hasSnapshot ? "snapshot" : "connecting";
}

export function shouldPollOfficialSnapshot(status) {
  return status === "snapshot" || status === "fallback";
}
