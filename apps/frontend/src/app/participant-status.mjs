export function participantStatusCounts(participants) {
  const active = participants.filter(participant => !participant.removed);
  return {
    configuring: active.filter(participant => participant.membership_status === 'configuring_strategy').length,
    ready: active.filter(participant => participant.membership_status === 'ready' || (!participant.membership_status && participant.ready)).length,
  };
}
