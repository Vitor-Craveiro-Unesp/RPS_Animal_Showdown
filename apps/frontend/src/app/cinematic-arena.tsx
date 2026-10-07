"use client";

import { useEffect, useRef, useState } from "react";
import { scheduledSteps, PresentationQueue, stateForPresentation } from "./presentation.mjs";
import { AudioManager } from "./audio-manager.mjs";

// Public DTOs only: this component never submits a competitive mutation.
type Player = { player_id: string; display_name: string; animal_id: string; second_chance?: boolean };
type Match = { match_id: string | null; player_one_id: string | null; player_two_id: string | null; player_one_hearts: number | null; player_two_hearts: number | null; initial_hearts: number | null; winner_id: string | null; loser_id: string | null; status: string | null };
type Round = { number: number | null; entrant_ids: string[]; matches: Match[]; bye_player_id: string | null; waiting_player_id?: string | null; second_chance_player_id?: string | null };
type State = { run_id?: string; presentation_state?: State; first_place?: string | null; second_place?: string | null; third_place?: string | null; state_version: number | null; champion_id: string | null; players: Player[]; current_round: Round | null; completed_rounds: Round[] };
type Event = { eventId: string; sequence: number; eventType: string; payload: any };
type Step = { phase: string; ms: number; startsAtMs: number; sound: string | null; event: Event; number?: number };
type Props = { podiumControls?: import("react").ReactNode; state: State | null; events: Event[]; queue: PresentationQueue; revision: number; movement: string; countdown: string; audio: AudioManager | null; emoji: (id: string | null) => string; u: (key: string) => string; realtime: string };

export default function CinematicArena({ podiumControls, state, events, queue, revision, movement, countdown, audio, emoji, u, realtime }: Props) {
  const [step, setStep] = useState<Step | null>(null);
  const [match, setMatch] = useState<Match | null>(null);
  const [presentationState, setPresentationState] = useState<State | null>(state?.presentation_state ?? state);
  const [podiumPresented, setPodiumPresented] = useState(() => Boolean(state?.champion_id && !state?.presentation_state && !queue.pending.length));
  const [visibleSequence, setVisibleSequence] = useState(() => queue.pending.length ? queue.pending[0].sequence - 1 : events.at(-1)?.sequence ?? 0);
  const stateRef = useRef(state);
  const roundTransitionRef = useRef<{ before: State | null; after: State | null; matchId: string | null } | null>(null);
  const stageRef = useRef<HTMLDivElement>(null);
  useEffect(() => { stateRef.current = state; }, [state]);
  const visibleState = presentationState ?? state;
  const allRounds = visibleState ? [...visibleState.completed_rounds, ...(visibleState.current_round ? [visibleState.current_round] : [])] : [];
  const player = (id: string | null) => visibleState?.players.find(item => item.player_id === id);

  const mascot = (id: string | null) => id ? emoji(id) + (player(id)?.second_chance ? '🧟' : '') : '';

  useEffect(() => {
    let stopped = false;
    let timer: ReturnType<typeof setTimeout>;
    let steps: Step[] = [];
    let generation = queue.generation;
    const pump = () => {
      if (stopped) return;
      if (generation !== queue.generation) {
        generation = queue.generation; steps = []; roundTransitionRef.current = null;
        setStep(null); setMatch(null); setPresentationState(stateRef.current?.presentation_state ?? stateRef.current);
        setPodiumPresented(Boolean(stateRef.current?.champion_id && !stateRef.current?.presentation_state));
        audio?.stop('effect'); audio?.stop('animal');
      }
      if (!steps.length) {
        const event = queue.next();
        if (event) {
          steps = scheduledSteps(event, Number(movement), Number(countdown)) as Step[];
          if (!steps.length && event.eventType !== 'podium_decided') setVisibleSequence(sequence => Math.max(sequence, event.sequence));
        }
      }
      const next = steps.shift();
      if (!next) {
        if (!queue.pending.length) { setStep(null); setMatch(null); }
        timer = setTimeout(pump, 60); return;
      }
      const untilStart = next.startsAtMs - Date.now();
      if (untilStart > 0) { steps.unshift(next); timer = setTimeout(pump, untilStart); return; }
      const onTime = next.ms === 0 || Date.now() < next.startsAtMs + next.ms;
      if (onTime) setStep(next);
      const payload = next.event.payload ?? {};
      const eventState = payload.state ?? stateRef.current;
      if (next.event.eventType === 'round_resolved' && next.phase === 'countdown' && next.number === 3) {
        roundTransitionRef.current = { before: payload.previousState ?? null, after: payload.state ?? null, matchId: payload.matchId ?? null };
      }
      const transition = roundTransitionRef.current;
      if (next.event.eventType === 'round_resolved') {
        if (next.phase === 'countdown' || next.phase === 'reveal' || next.phase === 'result') {
          if (transition?.before) setPresentationState(transition.before);
        }
        if (next.phase === 'result') setVisibleSequence(sequence => Math.max(sequence, next.event.sequence));
        if (next.phase === 'result' && payload.outcome === 'tie' && transition?.after) setPresentationState(transition.after);
      }
      if (next.phase === 'heart' && transition) setPresentationState(stateForPresentation(transition.before, transition.after, 'heart', transition.matchId));
      if (next.phase === 'victory' && transition?.after) setPresentationState(transition.after);
      if (next.phase === 'podium') setPodiumPresented(true);
      if (next.event.eventType !== 'round_resolved') setVisibleSequence(sequence => Math.max(sequence, next.event.sequence));
      const rounds: Round[] = eventState ? [...eventState.completed_rounds, ...(eventState.current_round ? [eventState.current_round] : [])] : [];
      const officialMatch = rounds.flatMap(round => round.matches).find(item => item.match_id === payload.matchId);
      const before = payload.previousState;
      const previousRounds: Round[] = before ? [...before.completed_rounds, ...(before.current_round ? [before.current_round] : [])] : [];
      const previousMatch = previousRounds.flatMap(round => round.matches).find(item => item.match_id === payload.matchId);
      if (next.phase === 'entrance' && officialMatch) setMatch({ ...officialMatch, player_one_hearts: officialMatch.initial_hearts, player_two_hearts: officialMatch.initial_hearts });
      if (next.phase === 'heart' || next.phase === 'elimination') setMatch(current => current ? { ...current, ...(payload.playerId === current.player_one_id ? { player_one_hearts: payload.heartsRemaining ?? 0 } : { player_two_hearts: payload.heartsRemaining ?? 0 }) } : officialMatch ?? null);
      if (next.phase === 'countdown') setMatch(current => current?.match_id === payload.matchId ? current : previousMatch ?? officialMatch ?? null);
      const eventPlayers = eventState?.players ?? stateRef.current?.players ?? [];
      const soundPlayer = eventPlayers.find((item: Player) => item.player_id === (payload.winnerId ?? payload.playerId));
      if (onTime && next.phase === 'victory' && soundPlayer) audio?.winner(soundPlayer.animal_id, Boolean(soundPlayer.second_chance));
      else if (onTime && next.phase === 'secondChance' && soundPlayer) audio?.animal(soundPlayer.animal_id, true);
      else if (onTime && next.sound) audio?.effect(next.sound);
      // Even the podium is scheduled by the server. Waiting for local audio
      // playback to resolve would make each viewer reveal places at a different time.
      timer = setTimeout(pump, Math.max(0, next.startsAtMs + next.ms - Date.now()));
    };
    timer = setTimeout(pump, 0);
    return () => { stopped = true; clearTimeout(timer); audio?.stop('effect'); audio?.stop('animal'); };
  }, [queue, audio, movement, countdown, revision]);

  useEffect(() => {
    if (!step || !['entrance','advance','bye'].includes(step.phase) || window.matchMedia('(prefers-reduced-motion: reduce)').matches) return;
    const root = stageRef.current;
    if (!root) return;
    const p = step.event.payload ?? {};
    const ids = step.phase === 'entrance' ? [p.playerOneId, p.playerTwoId] : [p.playerId];
    const animations: Animation[] = [];
    for (const id of ids) {
      const slots = Array.from(root.querySelectorAll<HTMLElement>('[data-slot]')).filter(node => node.dataset.slot === id);
      const fighter = Array.from(root.querySelectorAll<HTMLElement>('[data-fighter]')).find(node => node.dataset.fighter === id);
      const waiting = Array.from(root.querySelectorAll<HTMLElement>('[data-arrival]')).find(node => node.dataset.arrival === id);
      const destination = step.phase === 'entrance' ? fighter : slots.length > 1 ? slots.at(-1) : waiting;
      const origin = step.phase === 'entrance' ? slots[0] : fighter ?? slots[0];
      if (!destination || !origin || !destination.animate) continue;
      const a = origin.getBoundingClientRect(), b = destination.getBoundingClientRect();
      animations.push(destination.animate([{ transform:`translate(${a.x-b.x}px, ${a.y-b.y}px) scale(.75)`, opacity:.5 }, { transform:`translate(${a.x-b.x}px, 0) scale(.9)`, opacity:1, offset:.55 }, { transform:'translate(0,0) scale(1)', opacity:1 }], { duration:step.ms, easing:'ease-in-out' }));
    }
    return () => animations.forEach(animation => animation.cancel());
  }, [step]);

  const active = match ?? allRounds.flatMap(round => round.matches).find(item => item.status === 'active');
  const payload = step?.event.payload ?? {};
  const champion = step?.phase === 'champion' ? payload.playerId : null;
  const podium = ['podium_second', 'podium_third', 'podium'].includes(step?.phase ?? '') || (!step && podiumPresented && Boolean(visibleState?.champion_id));
  const podiumPlaces = step?.phase === 'podium_second' ? 2 : 3;
  const revealed = step && ['reveal','result'].includes(step.phase);
  const symbols: Record<string,string> = { rock:'✊', paper:'📄', scissors:'✂️' };
  const fighter = (id: string | null, lives: number | null, move: string) => <div className={`cinema-fighter ${step?.phase === 'elimination' && payload.playerId === id ? 'eliminated' : ''} ${step?.phase === 'victory' && payload.winnerId === id ? 'victorious' : ''}`}>
    <span className="cinema-mascot" data-fighter={id} title={player(id)?.second_chance ? `${u('zombie')} · ${u('secondChanceReturn')}` : undefined}>{mascot(id)}</span><b>{player(id)?.display_name}</b>
    <div className={`cinema-hearts ${step?.phase === 'heart' && payload.playerId === id ? 'heart-breaking' : ''}`} aria-label={`${u('heartsCount')}: ${lives ?? 0}`}>{'❤️'.repeat(Math.max(0,lives ?? 0))}{step?.phase === 'heart' && payload.playerId === id && <span>💔</span>}</div>
    <div className="cinema-move">{revealed ? <>{symbols[move]} <small>{u(move)}</small></> : ' '}</div>
  </div>;
  return <div className="cinematic-layout" ref={stageRef}>
    <div className="card cinema-stage">
      {step && ['advance','bye'].includes(step.phase) && <div className="cinema-transit"><span data-arrival={payload.playerId}>{mascot(payload.playerId)}</span><b>{player(payload.playerId)?.display_name}</b><span>{u(`cinema_${step.phase}`)}</span></div>}
      {champion ? <div className="cinema-champion"><h2>🏆 {player(champion)?.display_name}</h2><span className="cinema-mascot">{mascot(champion)}</span></div> : podium ? <div className="cinema-champion"><h2>🏆 {u('podium')}</h2><div className="official-podium">{[visibleState?.first_place ?? visibleState?.champion_id, visibleState?.second_place, visibleState?.third_place].map((id, index) => id && index < podiumPlaces && <section key={id} data-place={index + 1}><h3>{['🥇', '🥈', '🥉'][index]} {u(['firstPlace', 'secondPlace', 'thirdPlace'][index])}</h3><span className="cinema-mascot">{mascot(id)}</span><h2>{player(id)?.display_name}</h2></section>)}</div>{step?.phase === 'podium' || !step ? podiumControls : null}</div> : active ? <>
        {active.match_id?.endsWith(":third-place") && <h3>🥉 {u("thirdPlaceMatch")}</h3>}
        {allRounds.some(round => round.entrant_ids.length === 2 && round.matches.at(-1)?.match_id === active.match_id) && <h3>🏆 {u("grandFinal")}</h3>}
        {active.match_id?.endsWith(":second-chance") && <h3>🧟 {u("secondChance")}</h3>}
        <p className="small">{u('officialRound')} {payload.round ?? allRounds.find(round => round.matches.some(item => item.match_id === active.match_id))?.number}</p>
        <div className="cinema-duel">{fighter(active.player_one_id, active.player_one_hearts, payload.playerOneMove)}<div className="cinema-center" aria-live="polite">{step?.phase === 'countdown' ? <strong key={`${step.event.eventId}-${step.number}`} className="cinema-countdown">{step.number}</strong> : u('versus')}</div>{fighter(active.player_two_id, active.player_two_hearts, payload.playerTwoMove)}</div>
        <p className="cinema-caption" aria-live="polite">{step?.phase === 'result' ? payload.outcome === 'tie' ? u('cinemaTie') : `${u('cinemaRoundWinner')}: ${player(payload.lostHeartPlayerId === active.player_one_id ? active.player_two_id : active.player_one_id)?.display_name ?? ''}` : step ? u(`cinema_${step.phase}`) : u('status_pending')}</p>
      </> : <p>{u('status_pending')}</p>}
    </div>
<div className="card cinema-bracket"><h3>{u('cinemaBracket')}</h3><div className="cinema-rounds">{allRounds.map(round => <section key={round.number}><h4>{u('officialRound')} {round.number}</h4>{round.entrant_ids.length === 4 && <p>{u("semifinals")}</p>}{round.matches.map(item => <div className="bracket-match" key={item.match_id}>{item.match_id?.endsWith(":second-chance") && <h4>🧟 {u("secondChance")}</h4>}{item.match_id?.endsWith(":third-place") ? <h4>🥉 {u("thirdPlaceMatch")}</h4> : round.entrant_ids.length === 2 ? <h4>🏆 {u("grandFinal")}</h4> : null}{[item.player_one_id,item.player_two_id].map(id => <div key={id} className={`bracket-slot ${item.loser_id === id ? 'eliminated' : ''}`}><span data-slot={id} data-second-chance={player(id)?.second_chance || undefined}>{mascot(id)}</span><span>{player(id)?.display_name}</span>{item.loser_id === id ? '💀' : item.winner_id === id ? '✓' : ''}</div>)}</div>)}{round.waiting_player_id && <p>{mascot(round.waiting_player_id)} {player(round.waiting_player_id)?.display_name} · {u("secondChanceWaiting")}</p>}{round.bye_player_id && <div className="bracket-slot"><span data-slot={round.bye_player_id}>{mascot(round.bye_player_id)}</span>{player(round.bye_player_id)?.display_name} · {u('bye')}</div>}</section>)}</div></div>
    <div className="card cinema-events"><h3>{u('cinemaEvents')}</h3><p>{u('realtime')}: {u(realtime)}</p>{events.filter(event => event.sequence <= visibleSequence && (event.eventType !== 'podium_decided' || podiumPresented)).map(event => <p className="event" key={event.eventId} data-event-id={event.eventId}>#{event.sequence} · {u(`event_${event.eventType}`)} {mascot(event.payload?.playerId ?? event.payload?.winnerId ?? event.payload?.playerOneId)} {player(event.payload?.playerId ?? event.payload?.winnerId ?? event.payload?.playerOneId)?.display_name}{event.payload?.playerTwoId && <> {u("versus")} {mascot(event.payload.playerTwoId)} {player(event.payload.playerTwoId)?.display_name}</>}</p>)}</div>
  </div>;
}
