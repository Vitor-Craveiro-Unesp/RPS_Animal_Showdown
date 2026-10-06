export function requestFeedbackKind(status) {
  return status === 429 ? "rateLimited" : "network";
}
