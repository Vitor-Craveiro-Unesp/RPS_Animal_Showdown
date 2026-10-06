"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import Image from "next/image";
import CinematicArena from "./cinematic-arena";
import { PresentationQueue } from "./presentation.mjs";
import { AUDIO_ASSETS, AudioManager } from "./audio-manager.mjs";
import { requestFeedbackKind } from "./request-feedback.mjs";
import { realtimeDisplayStatus, shouldPollOfficialSnapshot } from "./realtime-status.mjs";
import { restoreTournamentSession, saveOrganizerSession, saveParticipantSession, saveTournamentView } from "./organizer-session.mjs";
import { animalName, animalShowcaseRows, Locale, localeNames, locales, regionName, scientificName, text, uiText } from "../i18n/catalog";
import { animalRushRoundDuration, randomAnimalRushMove, resolveAnimalRushAnswer, winningAnimalRushMove } from "./animal-rush.mjs";

const animals = [
  { id:"eagle", emoji:"🦅", x:248, y:102, country:"US", continent:"northAmerica" }, { id:"panda", emoji:"🐼", x:757, y:120, country:"CN", continent:"asia" },
  { id:"kangaroo", emoji:"🦘", x:852, y:335, country:"AU", continent:"oceania" }, { id:"otter", emoji:"🦦", x:296, y:54, country:"CA", continent:"northAmerica" },
  { id:"monkey", emoji:"🐵", x:839, y:112, country:"JP", continent:"asia" }, { id:"rooster", emoji:"🐓", x:482, y:82, country:"FR", continent:"europe" },
  { id:"bull", emoji:"🐂", x:486, y:106, country:"ES", continent:"europe" }, { id:"tiger", emoji:"🐯", x:709, y:161, country:"IN", continent:"asia" },
  { id:"elephant", emoji:"🐘", x:772, y:190, country:"TH", continent:"asia" }, { id:"bear", emoji:"🐻", x:695, y:48, country:"RU", continent:"asia" },
  { id:"octopus", emoji:"🐙", x:500, y:19, country:"arctic", continent:"arcticOcean" }, { id:"llama", emoji:"🦙", x:297, y:279, country:"PE", continent:"southAmerica" },
  { id:"white_tailed_deer", emoji:"🦌", x:266, y:179, country:"HN", continent:"northAmerica" }, { id:"camel", emoji:"🐪", x:618, y:178, country:"SA", continent:"asia" },
  { id:"goat", emoji:"🐐", x:678, y:138, country:"PK", continent:"asia" }, { id:"lizard", emoji:"🦎", x:822, y:254, country:"ID", continent:"asia" },
  { id:"angora_cat", emoji:"🐱", x:600, y:96, country:"TR", continent:"europe" }, { id:"zebra", emoji:"🦓", x:563, y:307, country:"BW", continent:"africa" },
  { id:"macaw", emoji:"🦜", x:355, y:284, country:"BR", continent:"southAmerica" }, { id:"crane", emoji:"🐦", x:581, y:231, country:"UG", continent:"africa" },
  { id:"lion", emoji:"🦁", x:605, y:248, country:"KE", continent:"africa" }, { id:"penguin", emoji:"🐧", x:500, y:460, country:"southPole", continent:"antarctica" },
  { id:"gorilla", emoji:"🦍", x:576, y:257, country:"RW", continent:"africa" }, { id:"hilsa", emoji:"🐟", x:739, y:177, country:"BD", continent:"asia" },
  { id:"horse", emoji:"🐎", x:358, y:351, country:"UY", continent:"southAmerica" }, { id:"shark", emoji:"🦈", x:438, y:190, country:"CV", continent:"africa" },
] as const;

type Screen = "home" | "create" | "join" | "strategy" | "waiting" | "animal-rush" | "animal-rush-result" | "training-avatar" | "training" | "training-complete" | "guest-animal" | "guest-training-avatar" | "guest-strategy" | "guest-training" | "guest-training-complete" | "organizer" | "arena";
type AnimalRushMove = "rock" | "paper" | "scissors";
type AnimalRushFeedback = "correct" | "incorrect" | "timeout" | null;
type Distribution = { rock: number; paper: number; scissors: number };
type Participant = { player_id: string; display_name: string; animal_id: string; ready: boolean; strategy_locked: boolean; membership_status?: string; removed?: boolean };
type TrainingRound = { number: number; manual_move: string; character_move: string; manual_hearts: number; character_hearts: number };
type TrainingState = { manual_hearts?: number; character_hearts?: number; rounds?: TrainingRound[]; status?: "active" | "completed"; winner?: "manual_player" | "character" };
const trainingAvatars = [
  { id: "man", emoji: "👨🏻", label: "trainerMan" }, { id: "woman", emoji: "👩‍🦰", label: "trainerWoman" },
  { id: "boy", emoji: "👱‍♂️", label: "trainerBoy" }, { id: "girl", emoji: "👧🏿", label: "trainerGirl" },
  { id: "baby", emoji: "👶🏾", label: "trainerBaby" }, { id: "alien", emoji: "👽", label: "trainerAlien" },
  { id: "older-man", emoji: "👴🏻", label: "trainerOlderMan" }, { id: "older-woman", emoji: "👵🏿", label: "trainerOlderWoman" },
] as const;
type TrainingAvatar = (typeof trainingAvatars)[number];
type MatchFormat = 1 | 3 | 5 | 7;
type PlaybackSpeed = "0.5" | "1" | "2" | "4" | "8";
type OfficialPlayer = { player_id: string; display_name: string; animal_id: string };
type OfficialRound = { number: number | null; entrant_ids: string[]; bye_player_id: string | null; matches: OfficialMatch[] };
type OfficialMatch = { match_id: string | null; status: string | null; player_one_id: string | null; player_two_id: string | null; initial_hearts: number | null; player_one_hearts: number | null; player_two_hearts: number | null; winner_id: string | null; loser_id: string | null; rounds: Array<{ number: number | null; player_one_move: string | null; player_two_move: string | null; outcome: string | null }> };
type OfficialState = { run_id?: string; run_start_sequence?: number; first_place?: string | null; second_place?: string | null; third_place?: string | null; sound_effects_enabled?: boolean; background_music_enabled?: boolean; movement_speed?: PlaybackSpeed; countdown_speed?: PlaybackSpeed; tournament_id: string; state_version: number | null; status: string | null; hearts_per_match: number | null; champion_id: string | null; players: OfficialPlayer[]; current_round: OfficialRound | null; completed_rounds: OfficialRound[] };
type OfficialEvent = { eventId: string; sequence: number; eventType: string; payload: unknown };
const animalRushEmoji: Record<AnimalRushMove, string> = { rock: "✊", paper: "📄", scissors: "✂️" };
const tournamentRealtimeScreens = new Set<Screen>(["waiting", "animal-rush", "animal-rush-result", "training-avatar", "training", "training-complete", "arena"]);
const savedAudioPreference = (key: string) => {
  if (typeof window === "undefined") return true;
  try { return window.localStorage.getItem(key) !== "false"; } catch { return true; }
};
const resetTrainingChampionCue = (reference: { current: string | null }) => { reference.current = null; };
const playbackSpeeds: ReadonlyArray<{ value: PlaybackSpeed; label: string }> = [
  { value: "0.5", label: "speed05" },
  { value: "1", label: "speed1" },
  { value: "2", label: "speed2" },
  { value: "4", label: "speed4" },
  { value: "8", label: "speed8" },
];
const strategyConditions = ["initial", "lost_to_rock", "lost_to_paper", "lost_to_scissors", "won_against_rock", "won_against_paper", "won_against_scissors", "tied_with_rock", "tied_with_paper", "tied_with_scissors"] as const;
const conditionLabels: Record<string, Record<string, string>> = {
  "pt-BR": { initial:"Inicial", lost_to_rock:"Perdeu para Pedra", lost_to_paper:"Perdeu para Papel", lost_to_scissors:"Perdeu para Tesoura", won_against_rock:"Venceu contra Pedra", won_against_paper:"Venceu contra Papel", won_against_scissors:"Venceu contra Tesoura", tied_with_rock:"Empatou com Pedra", tied_with_paper:"Empatou com Papel", tied_with_scissors:"Empatou com Tesoura" },
  en: { initial:"Initial", lost_to_rock:"Lost to Rock", lost_to_paper:"Lost to Paper", lost_to_scissors:"Lost to Scissors", won_against_rock:"Won against Rock", won_against_paper:"Won against Paper", won_against_scissors:"Won against Scissors", tied_with_rock:"Tied with Rock", tied_with_paper:"Tied with Paper", tied_with_scissors:"Tied with Scissors" },
  "zh-CN": { initial:"初始", lost_to_rock:"输给石头", lost_to_paper:"输给布", lost_to_scissors:"输给剪刀", won_against_rock:"赢过石头", won_against_paper:"赢过布", won_against_scissors:"赢过剪刀", tied_with_rock:"与石头平局", tied_with_paper:"与布平局", tied_with_scissors:"与剪刀平局" },
  ar: { initial:"الافتتاحية", lost_to_rock:"خسر أمام حجر", lost_to_paper:"خسر أمام ورق", lost_to_scissors:"خسر أمام مقص", won_against_rock:"فاز على حجر", won_against_paper:"فاز على ورق", won_against_scissors:"فاز على مقص", tied_with_rock:"تعادل مع حجر", tied_with_paper:"تعادل مع ورق", tied_with_scissors:"تعادل مع مقص" },
};
const defaultStrategy = (): Record<string, Distribution> => Object.fromEntries(strategyConditions.map((key) => [key, { rock: 33, paper: 33, scissors: 34 }]));

export default function HomePage() {
  const [locale, setLocale] = useState<Locale>("pt-BR");
  const [screen, setScreen] = useState<Screen>("home");
  const [code, setCode] = useState("");
  const [name, setName] = useState("");
  const [animal, setAnimal] = useState<(typeof animals)[number]>(animals[1]);
  const [mapZoomed, setMapZoomed] = useState(false);
  const [strategy, setStrategy] = useState<Record<string, Distribution>>(defaultStrategy);
  const [condition, setCondition] = useState<string>("initial");
  const [capacity, setCapacity] = useState(8);
  const [matchFormat, setMatchFormat] = useState<MatchFormat>(3);
  const [heartsRequired, setHeartsRequired] = useState(2);
  const [movementSpeed, setMovementSpeed] = useState<PlaybackSpeed>("1");
  const [countdownSpeed, setCountdownSpeed] = useState<PlaybackSpeed>("1");
  const [soundEffectsEnabled, setSoundEffectsEnabled] = useState(true);
  const [backgroundMusicEnabled, setBackgroundMusicEnabled] = useState(true);
  // Tournament settings are an organizer-controlled upper bound. These two
  // settings are local to this browser, so a participant can always opt out
  // without changing the experience for anybody else.
  // Keep the server and the first client render identical. Browser preferences
  // are restored only after hydration, then persisted on subsequent changes.
  const [playerSoundEffectsEnabled, setPlayerSoundEffectsEnabled] = useState(true);
  const [playerBackgroundMusicEnabled, setPlayerBackgroundMusicEnabled] = useState(true);
  const [playerAudioPreferencesLoaded, setPlayerAudioPreferencesLoaded] = useState(false);
  const [organizerToken, setOrganizerToken] = useState("");
  const [playerToken, setPlayerToken] = useState("");
  const [tournamentId, setTournamentId] = useState("");
  const [createBusy, setCreateBusy] = useState(false);
  const [sessionRestored, setSessionRestored] = useState(false);
  const [participants, setParticipants] = useState<Participant[]>([]);
  const [requestFailed, setRequestFailed] = useState(false);
  const [requestRateLimited, setRequestRateLimited] = useState(false);
  const [trainingState, setTrainingState] = useState<TrainingState | null>(null);
  const [trainingAvatar, setTrainingAvatar] = useState<TrainingAvatar | null>(null);
  const [guestTrainingId, setGuestTrainingId] = useState("");
  const [guestHearts, setGuestHearts] = useState<number | null>(null);
  const [hoveredGuestHearts, setHoveredGuestHearts] = useState(0);
  const [presentationQueue] = useState(() => new PresentationQueue());
  const [presentationRevision, setPresentationRevision] = useState(0);
  const [audio, setAudio] = useState<AudioManager | null>(null);
  const selectionAudioRef = useRef<HTMLAudioElement | null>(null);
  const effectiveSoundEffectsEnabled = soundEffectsEnabled && playerSoundEffectsEnabled;
  const effectiveBackgroundMusicEnabled = backgroundMusicEnabled && playerBackgroundMusicEnabled;
  const reportRequestFailure = (response?: Response) => {
    setRequestRateLimited(requestFeedbackKind(response?.status) === "rateLimited");
    setRequestFailed(true);
  };
  const clearRequestFailure = () => {
    setRequestRateLimited(false);
    setRequestFailed(false);
  };
  useEffect(() => {
    const timer = window.setTimeout(() => {
      setPlayerSoundEffectsEnabled(savedAudioPreference("rps-player-sound-effects"));
      setPlayerBackgroundMusicEnabled(savedAudioPreference("rps-player-background-music"));
      setPlayerAudioPreferencesLoaded(true);
    }, 0);
    return () => window.clearTimeout(timer);
  }, []);
  useEffect(() => {
    if (!playerAudioPreferencesLoaded) return;
    try {
      window.localStorage.setItem("rps-player-sound-effects", String(playerSoundEffectsEnabled));
      window.localStorage.setItem("rps-player-background-music", String(playerBackgroundMusicEnabled));
    } catch {}
  }, [playerAudioPreferencesLoaded, playerSoundEffectsEnabled, playerBackgroundMusicEnabled]);
  useEffect(() => {
    const manager = new AudioManager(window);
    const timer = window.setTimeout(() => setAudio(manager), 0);
    const unlock = () => manager.unlock();
    window.addEventListener("pointerdown", unlock, { once: true });
    window.addEventListener("keydown", unlock, { once: true });
    return () => { clearTimeout(timer); window.removeEventListener("pointerdown", unlock); window.removeEventListener("keydown", unlock); manager.dispose(); };
  }, []);
  useEffect(() => {
    audio?.stopAll();
    // Background music is intentionally available across the whole experience;
    // it remains silent whenever either the organizer or the player disables it.
    audio?.configure(effectiveSoundEffectsEnabled, effectiveBackgroundMusicEnabled);
    return () => audio?.stopAll();
  }, [audio, screen, effectiveSoundEffectsEnabled, effectiveBackgroundMusicEnabled]);
  useEffect(() => { audio?.cancelSpeech(); }, [audio, locale]);
  useEffect(() => {
    if (!audio || !["training-complete", "guest-training-complete"].includes(screen) || trainingState?.status !== "completed") return;
    const cue = `${screen}:${guestTrainingId}:${trainingState.rounds?.length ?? 0}`;
    if (trainingChampionCueRef.current === cue) return;
    trainingChampionCueRef.current = cue;
    audio.effect("champion");
  }, [audio, screen, trainingState, guestTrainingId]);
  const chooseAnimal = (item: (typeof animals)[number]) => {
    setAnimal(item);
    // Selection is a direct user gesture. Keep it independent from the
    // asynchronous hydration effect so the very first mascot can speak too.
    const manager = audio ?? new AudioManager(window);
    if (!audio) setAudio(manager);
    manager.configure(effectiveSoundEffectsEnabled, effectiveBackgroundMusicEnabled);
    // `play()` runs within the original click gesture. This avoids a browser
    // autoplay rejection that can happen when playback waits for a React render.
    const media = selectionAudioRef.current;
    if (effectiveSoundEffectsEnabled && media) {
      try {
        media.pause(); media.currentTime = 0; media.src = AUDIO_ASSETS.animals[item.id]; media.load();
        void media.play().catch(() => {});
      } catch {}
    }
  };
  const narrateAnimal = (event: React.MouseEvent) => { event.stopPropagation(); selectionAudioRef.current?.pause(); audio?.narrate(animalName(locale, animal.id), scientificName(animal.id), locale); };
  const startTrainingAudio = () => {
    const manager = audio ?? new AudioManager(window);
    if (!audio) setAudio(manager);
    // This is invoked directly by the training-start click, satisfying browser
    // gesture requirements before the asynchronous training request resolves.
    manager.configure(effectiveSoundEffectsEnabled, effectiveBackgroundMusicEnabled);
  };
  const updatePlayerAudioPreferences = (nextEffects: boolean, nextMusic: boolean) => {
    setPlayerSoundEffectsEnabled(nextEffects);
    setPlayerBackgroundMusicEnabled(nextMusic);
    const manager = audio ?? new AudioManager(window);
    if (!audio) setAudio(manager);
    manager.unlock();
    manager.configure(soundEffectsEnabled && nextEffects, backgroundMusicEnabled && nextMusic);
  };
  const reconcilePresentation = useCallback((version: number) => {
    presentationQueue.reconcile(version);
    setPresentationRevision(current => current + 1);
  }, [presentationQueue]);
  const [officialState, setOfficialState] = useState<OfficialState | null>(null);
  const [officialEvents, setOfficialEvents] = useState<OfficialEvent[]>([]);
  const [realtimeStatus, setRealtimeStatus] = useState<"connecting" | "snapshot" | "live" | "fallback">("connecting");
  const [rushPrompt, setRushPrompt] = useState<AnimalRushMove>("rock");
  const [rushScore, setRushScore] = useState(0);
  const [rushStreak, setRushStreak] = useState(0);
  const [rushBestStreak, setRushBestStreak] = useState(0);
  const [rushEndedStreak, setRushEndedStreak] = useState(0);
  const [rushFeedback, setRushFeedback] = useState<AnimalRushFeedback>(null);
  const [rushCorrectAnswer, setRushCorrectAnswer] = useState<AnimalRushMove | null>(null);
  const [officialStartNotice, setOfficialStartNotice] = useState(false);
  const lastSequenceRef = useRef(0);
  const eventsRef = useRef<OfficialEvent[]>([]);
  const latestVersionRef = useRef(0);
  const lastOfficialStateRef = useRef<OfficialState | null>(null);
  const repeatCommandRef = useRef<{ run: string; key: string } | null>(null);
  const repeatBusyRef = useRef(false);
  const [repeatBusy, setRepeatBusy] = useState(false);
  const trainingChampionCueRef = useRef<string | null>(null);
  const synchronizeRun = useCallback((state: OfficialState) => {
    const oldRun = lastOfficialStateRef.current?.run_id;
    if (state.run_id && state.run_id !== oldRun) {
      presentationQueue.reset();
      audio?.resetRun();
      eventsRef.current = eventsRef.current.filter(event => (event.payload as { runId?: string })?.runId === state.run_id);
      setOfficialEvents(eventsRef.current);
      setPresentationRevision(current => current + 1);
    }
    if (state.run_start_sequence) lastSequenceRef.current = Math.max(lastSequenceRef.current, state.run_start_sequence - 1);
  }, [audio, presentationQueue]);
  const tournamentStartedRef = useRef(false);
  const animalRushTimerRef = useRef<number | null>(null);
  const officialStartNoticeTimerRef = useRef<number | null>(null);
  useEffect(() => {
    presentationQueue.reset();
    latestVersionRef.current = 0;
    lastOfficialStateRef.current = null;
  }, [presentationQueue, tournamentId]);
  const t = (key: any) => text(locale, key);
  const u = (key: string) => uiText(locale, key);
  const homeActionLabel = (key: string) => u(key).split("\n").map((line, index) => <span key={`${key}-${index}`}>{line}</span>);
  const homeActionAria = (key: string) => u(key).replace("\n", " ");
  const requestFailureMessage = requestRateLimited ? t("rateLimited") : t("network");
  const distribution = strategy[condition];
  const total = distribution.rock + distribution.paper + distribution.scissors;
  const completed = strategyConditions.filter((key) => strategy[key].rock + strategy[key].paper + strategy[key].scissors === 100).length;
  const validStrategy = completed === strategyConditions.length;
  const updateDistribution = (move: keyof Distribution, value: number) => setStrategy((current) => ({ ...current, [condition]: { ...current[condition], [move]: value } }));
  const randomDistribution = (): Distribution => {
    const rock = Math.floor(Math.random() * 101);
    const paper = Math.floor(Math.random() * (101 - rock));
    return { rock, paper, scissors: 100 - rock - paper };
  };
  const randomize = () => setStrategy((current) => ({ ...current, [condition]: randomDistribution() }));
  const randomizeAll = () => setStrategy(Object.fromEntries(strategyConditions.map((key) => [key, randomDistribution()])));
  const selectedAnimalName = animalName(locale, animal.id);
  const guestTraining = screen === "guest-training" || screen === "guest-training-complete";
  const hearts = (count = guestTraining ? (guestHearts ?? 1) : heartsRequired) => "❤️".repeat(count);
  const realtimeEligible = tournamentRealtimeScreens.has(screen);
  const rushRoundMs = animalRushRoundDuration(rushStreak);

  const clearAnimalRushTimer = useCallback(() => {
    if (animalRushTimerRef.current !== null) {
      window.clearTimeout(animalRushTimerRef.current);
      animalRushTimerRef.current = null;
    }
  }, []);

  const interruptForOfficialStart = useCallback(() => {
    tournamentStartedRef.current = true;
    clearAnimalRushTimer();
    setRushScore(0);
    setRushStreak(0);
    setRushEndedStreak(0);
    setRushFeedback(null);
    setRushCorrectAnswer(null);
    setTrainingState(null);
    setTrainingAvatar(null);
    setOfficialStartNotice(true);
    if (officialStartNoticeTimerRef.current !== null) window.clearTimeout(officialStartNoticeTimerRef.current);
    officialStartNoticeTimerRef.current = window.setTimeout(() => setOfficialStartNotice(false), 1_600);
    setScreen("arena");
  }, [clearAnimalRushTimer]);

  useEffect(() => {
    const timer = window.setTimeout(() => {
      const session = restoreTournamentSession(sessionStorage);
      const savedScreen = session.screen;
      if (savedScreen && ["training-avatar", "training", "training-complete", "animal-rush", "animal-rush-result"].includes(savedScreen)) setScreen("waiting");
      else if (savedScreen && ["home", "create", "join", "strategy", "waiting", "organizer", "arena"].includes(savedScreen)) setScreen(savedScreen as Screen);
      setCode(session.code);
      setOrganizerToken(session.organizerToken);
      setPlayerToken(session.playerToken);
      setTournamentId(session.tournamentId);
      setSessionRestored(true);
    }, 0);
    return () => window.clearTimeout(timer);
  }, []);

  useEffect(() => {
    if (!sessionRestored) return;
    saveTournamentView(sessionStorage, {
      screen: screen === "animal-rush" || screen === "animal-rush-result" ? "waiting" : screen,
      code,
      tournamentId,
    });
  }, [code, screen, sessionRestored, tournamentId]);

  useEffect(() => {
    clearAnimalRushTimer();
    if (screen !== "animal-rush" || tournamentStartedRef.current) return;
    animalRushTimerRef.current = window.setTimeout(() => {
      setRushEndedStreak(rushStreak);
      setRushCorrectAnswer(winningAnimalRushMove(rushPrompt));
      setRushFeedback("timeout");
      setRushStreak(0);
      setScreen("animal-rush-result");
    }, rushRoundMs);
    return clearAnimalRushTimer;
  }, [clearAnimalRushTimer, rushPrompt, rushRoundMs, rushStreak, screen]);

  useEffect(() => () => {
    clearAnimalRushTimer();
    if (officialStartNoticeTimerRef.current !== null) window.clearTimeout(officialStartNoticeTimerRef.current);
  }, [clearAnimalRushTimer]);

  useEffect(() => {
    if (screen !== "organizer" || !code || !organizerToken) return;
    const loadParticipants = async () => {
      const response = await fetch(`/api/v1/tournaments/${encodeURIComponent(code)}/admin/participants`, { headers: { Authorization: `Bearer ${organizerToken}` } });
      if (!response.ok) return reportRequestFailure(response);
      const payload = await response.json();
      setParticipants(Array.isArray(payload.participants) ? payload.participants : []);
    };
    void loadParticipants();
    const timer = window.setInterval(() => void loadParticipants(), 10_000);
    return () => window.clearInterval(timer);
  }, [code, organizerToken, screen]);

  useEffect(() => {
    if (!realtimeEligible || !code || !playerToken || realtimeStatus !== "fallback") return;
    const refreshStatus = async () => {
      const response = await fetch(`/api/v1/tournaments/${encodeURIComponent(code)}/players/me`, { headers: { Authorization: `Bearer ${playerToken}` } });
      if (!response.ok) return reportRequestFailure(response);
      const payload = await response.json();
      if (typeof payload.hearts_required === "number") setHeartsRequired(payload.hearts_required);
      if (typeof payload.movement_speed === "string") setMovementSpeed(payload.movement_speed as PlaybackSpeed);
      if (typeof payload.countdown_speed === "string") setCountdownSpeed(payload.countdown_speed as PlaybackSpeed);
      if (payload.tournament_started === true) interruptForOfficialStart();
    };
    void refreshStatus();
    const timer = window.setInterval(() => void refreshStatus(), 15_000);
    return () => window.clearInterval(timer);
  }, [code, interruptForOfficialStart, playerToken, realtimeEligible, realtimeStatus, reconcilePresentation]);

  useEffect(() => {
    if (!shouldPollOfficialSnapshot(realtimeStatus) || !code || !(organizerToken || playerToken) || !realtimeEligible) return;
    let disposed = false;
    const refreshOfficial = async () => {
      const token = playerToken || organizerToken;
      try {
        const response = await fetch(`/api/v1/tournaments/${encodeURIComponent(code)}/official-state`, {
          headers: { Authorization: `Bearer ${token}` },
        });
        if (response.status === 409) return;
        if (!response.ok) throw new Error("official-state unavailable");
        const payload = await response.json() as OfficialState;
        if (disposed) return;
        const version = payload.state_version ?? 0;
        if (version >= latestVersionRef.current) {
          synchronizeRun(payload);
          latestVersionRef.current = version;
          lastOfficialStateRef.current = payload;
          setOfficialState(payload);
          reconcilePresentation(version);
          if (typeof payload.sound_effects_enabled === "boolean") setSoundEffectsEnabled(payload.sound_effects_enabled);
          if (typeof payload.background_music_enabled === "boolean") setBackgroundMusicEnabled(payload.background_music_enabled);
          if (payload.movement_speed) setMovementSpeed(payload.movement_speed);
          if (payload.countdown_speed) setCountdownSpeed(payload.countdown_speed);
        }
        if (typeof payload.hearts_per_match === "number") setHeartsRequired(payload.hearts_per_match);
        interruptForOfficialStart();
      } catch { if (!disposed) reportRequestFailure(); }
    };
    void refreshOfficial();
    const timer = window.setInterval(() => void refreshOfficial(), 15_000);
    return () => { disposed = true; window.clearInterval(timer); };
  }, [code, interruptForOfficialStart, organizerToken, playerToken, realtimeEligible, realtimeStatus, reconcilePresentation, synchronizeRun]);

  useEffect(() => {
    if (!sessionRestored || !realtimeEligible || !code || !(organizerToken || playerToken)) return;
    let disposed = false;
    let socket: WebSocket | null = null;
    let retryTimer: number | undefined;
    let attempt = 0;
    let hasSynchronizedSnapshot = Boolean(lastOfficialStateRef.current);
    let websocketSubscribed = false;
    const accessToken = organizerToken || playerToken;
    const sequenceKey = `rps-realtime-sequence:${tournamentId || code}`;
    const eventsKey = `rps-realtime-events:${tournamentId || code}`;
    lastSequenceRef.current = Number(sessionStorage.getItem(sequenceKey) ?? "0") || 0;
    try {
      const stored = JSON.parse(sessionStorage.getItem(eventsKey) ?? "[]") as OfficialEvent[];
      eventsRef.current = Array.isArray(stored) ? stored.filter((event) => typeof event.eventId === "string" && typeof event.sequence === "number" && typeof event.eventType === "string").slice(-50) : [];
      window.setTimeout(() => { if (!disposed) setOfficialEvents(eventsRef.current); }, 0);
    } catch { eventsRef.current = []; }

    const loadSnapshot = async () => {
      const response = await fetch(`/api/v1/tournaments/${encodeURIComponent(code)}/official-state`, { headers: { Authorization: `Bearer ${accessToken}` } });
      if (response.status === 409) return null;
      if (!response.ok) throw new Error("official-state unavailable");
      const payload = await response.json() as OfficialState;
      if (!disposed) {
        hasSynchronizedSnapshot = true;
        setRealtimeStatus(realtimeDisplayStatus({ hasSnapshot: true, websocketSubscribed }));
        const version = payload.state_version ?? 0;
        if (version >= latestVersionRef.current) {
          synchronizeRun(payload);
          latestVersionRef.current = version;
          lastOfficialStateRef.current = payload;
          setOfficialState(payload);
          reconcilePresentation(version);
          if (typeof payload.sound_effects_enabled === "boolean") setSoundEffectsEnabled(payload.sound_effects_enabled);
          if (typeof payload.background_music_enabled === "boolean") setBackgroundMusicEnabled(payload.background_music_enabled);
          if (payload.movement_speed) setMovementSpeed(payload.movement_speed);
          if (payload.countdown_speed) setCountdownSpeed(payload.countdown_speed);
        }
        if (typeof payload.hearts_per_match === "number") setHeartsRequired(payload.hearts_per_match);
        interruptForOfficialStart();
      }
      return payload;
    };
    const scheduleReconnect = () => {
      if (disposed) return;
      websocketSubscribed = false;
      setRealtimeStatus(realtimeDisplayStatus({ hasSnapshot: hasSynchronizedSnapshot, websocketSubscribed }));
      if (attempt >= 5) { setRealtimeStatus("fallback"); return; }
      const delay = Math.min(1_000 * 2 ** attempt, 16_000);
      attempt += 1;
      retryTimer = window.setTimeout(connect, delay);
    };
    const endpoint = () => {
      const configured = process.env.NEXT_PUBLIC_REALTIME_URL;
      if (configured) return configured;
      return `${window.location.protocol === "https:" ? "wss" : "ws"}://${window.location.hostname}:8000/v1/realtime`;
    };
    const connect = async () => {
      setRealtimeStatus(realtimeDisplayStatus({ hasSnapshot: hasSynchronizedSnapshot, websocketSubscribed }));
      try {
        const ticketResponse = await fetch(`/api/v1/tournaments/${encodeURIComponent(code)}/realtime/ticket`, { method: "POST", headers: { Authorization: `Bearer ${accessToken}` } });
        if (!ticketResponse.ok) throw new Error("ticket unavailable");
        const { ticket } = await ticketResponse.json() as { ticket: string };
        // Establish the presentation version barrier before replay can arrive.
        await loadSnapshot();
        if (disposed) return;
        socket = new WebSocket(endpoint());
        socket.onopen = () => socket?.send(JSON.stringify({ type: "authenticate", ticket, channel: `tournament/${tournamentId}/official-events` }));
        socket.onmessage = (message) => {
          let frame: Record<string, unknown>;
          try { frame = JSON.parse(String(message.data)) as Record<string, unknown>; } catch { return; }
          if (frame.type === "subscribed") { attempt = 0; websocketSubscribed = true; setRealtimeStatus(realtimeDisplayStatus({ hasSnapshot: hasSynchronizedSnapshot, websocketSubscribed })); socket?.send(JSON.stringify({ type: "resume", afterSequence: lastSequenceRef.current })); return; }
          if (frame.type === "replay-reset" && Number.isSafeInteger(frame.afterSequence) && Number(frame.afterSequence) >= 0) {
            lastSequenceRef.current = Math.max(lastSequenceRef.current, Number(frame.afterSequence));
            sessionStorage.setItem(sequenceKey, String(lastSequenceRef.current));
            return;
          }
          if (frame.type !== "official-event" || frame.tournamentId !== tournamentId || typeof frame.eventId !== "string" || typeof frame.sequence !== "number" || typeof frame.eventType !== "string") return;
          const sequence = frame.sequence;
          if (sequence <= lastSequenceRef.current) return;
          if (sequence > lastSequenceRef.current + 1) { void loadSnapshot().catch(() => setRealtimeStatus("fallback")); socket?.send(JSON.stringify({ type: "resume", afterSequence: lastSequenceRef.current })); return; }
          lastSequenceRef.current = sequence;
          sessionStorage.setItem(sequenceKey, String(sequence));
          const incoming = frame.payload as { runId?: string; stateVersion?: number; state?: OfficialState } | null;
          if (incoming?.runId && lastOfficialStateRef.current?.run_id !== incoming.runId && (incoming.stateVersion ?? 0) < latestVersionRef.current) return;
          if (incoming?.state && (incoming.state.state_version ?? 0) >= latestVersionRef.current) synchronizeRun(incoming.state);
          if (!eventsRef.current.some((event) => event.eventId === frame.eventId)) {
            const visualEvent = { eventId: frame.eventId, sequence, eventType: frame.eventType, payload: { ...(frame.payload as Record<string, unknown>), previousState: lastOfficialStateRef.current } };
            presentationQueue.accept(visualEvent);
            eventsRef.current = [...eventsRef.current, { eventId: frame.eventId, sequence, eventType: frame.eventType, payload: frame.payload }].slice(-50);
            sessionStorage.setItem(eventsKey, JSON.stringify(eventsRef.current));
            setOfficialEvents(eventsRef.current);
          }
          const eventPayload = frame.payload && typeof frame.payload === "object" ? frame.payload as Record<string, unknown> : null;
          const eventState = eventPayload?.state as OfficialState | undefined;
          if (eventState?.tournament_id === tournamentId && typeof eventState.state_version === "number" && eventState.state_version >= latestVersionRef.current) {
            latestVersionRef.current = eventState.state_version;
            lastOfficialStateRef.current = eventState;
            setOfficialState(eventState);
            if (!tournamentStartedRef.current) interruptForOfficialStart();
          }
          if (frame.eventType === "tournament_started") { interruptForOfficialStart(); void loadSnapshot().catch(() => setRealtimeStatus("fallback")); }
        };
        socket.onclose = () => { websocketSubscribed = false; presentationQueue.clear(); audio?.stop("arena"); scheduleReconnect(); };
        socket.onerror = () => socket?.close();
      } catch { void loadSnapshot().catch(() => undefined); scheduleReconnect(); }
    };
    void connect();
    return () => { disposed = true; if (retryTimer) window.clearTimeout(retryTimer); socket?.close(); };
  }, [code, interruptForOfficialStart, organizerToken, playerToken, realtimeEligible, sessionRestored, tournamentId, reconcilePresentation, audio, presentationQueue, synchronizeRun]);

  async function createTournament() {
    if (createBusy) return;
    setCreateBusy(true);
    try {
      const response = await fetch("/api/v1/tournaments", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          capacity,
          hearts_required: Math.ceil(matchFormat / 2),
          sound_effects_enabled: soundEffectsEnabled,
          background_music_enabled: backgroundMusicEnabled,
          movement_speed: movementSpeed,
          countdown_speed: countdownSpeed,
        }),
      });
      if (!response.ok) {
        reportRequestFailure(response);
        return;
      }
      clearRequestFailure();
      tournamentStartedRef.current = false;
      const tournament = await response.json();
      setCode(tournament.tournament_code);
      setTournamentId(tournament.tournament_id);
      setOrganizerToken(tournament.organizer_access_token);
      setPlayerToken("");
      setHeartsRequired(tournament.hearts_required);
      saveOrganizerSession(sessionStorage, {
        code: tournament.tournament_code,
        tournamentId: tournament.tournament_id,
        organizerToken: tournament.organizer_access_token,
      });
      setScreen("organizer");
    } catch {
      reportRequestFailure();
    } finally {
      setCreateBusy(false);
    }
  }

  async function readyForTournament() {
    if (!code.trim() || !name.trim() || !validStrategy) return reportRequestFailure();
    let capability = playerToken;
    if (!capability) {
      const joined = await fetch("/api/v1/tournaments/join", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ tournament_code: code, display_name: name, animal_id: animal.id }) });
      if (!joined.ok) return reportRequestFailure(joined);
      const payload = await joined.json();
      capability = payload.player_access_token;
      setTournamentId(payload.tournament_id);
      if (typeof payload.hearts_required === "number") setHeartsRequired(payload.hearts_required);
      if (typeof payload.movement_speed === "string") setMovementSpeed(payload.movement_speed as PlaybackSpeed);
      if (typeof payload.countdown_speed === "string") setCountdownSpeed(payload.countdown_speed as PlaybackSpeed);
      setPlayerToken(capability);
      setOrganizerToken("");
      saveParticipantSession(sessionStorage, {
        code: payload.tournament_code,
        tournamentId: payload.tournament_id,
        playerToken: capability,
      });
    }
    const headers = { "Content-Type": "application/json", Authorization: `Bearer ${capability}` };
    const strategyResponse = await fetch(`/api/v1/tournaments/${encodeURIComponent(code)}/players/me/strategy`, { method: "PUT", headers, body: JSON.stringify(strategy) });
    if (!strategyResponse.ok) return reportRequestFailure(strategyResponse);
    const readyResponse = await fetch(`/api/v1/tournaments/${encodeURIComponent(code)}/players/me/ready`, { method: "POST", headers, body: "{}" });
    if (!readyResponse.ok) return reportRequestFailure(readyResponse);
    clearRequestFailure();
    setScreen("waiting");
  }

  async function startTournament() {
    const response = await fetch(`/api/v1/tournaments/${encodeURIComponent(code)}/admin/start`, { method: "POST", headers: { "Content-Type": "application/json", Authorization: `Bearer ${organizerToken}`, "Idempotency-Key": crypto.randomUUID() }, body: "{}" });
    if (!response.ok) return reportRequestFailure(response);
    clearRequestFailure();
    tournamentStartedRef.current = true;
    // The Start response is authoritative, but the organizer must not wait for
    // a later WebSocket handshake before receiving the server snapshot.
    try {
      const snapshot = await fetch(`/api/v1/tournaments/${encodeURIComponent(code)}/official-state`, { headers: { Authorization: `Bearer ${organizerToken}` } });
      if (!snapshot.ok) throw new Error("official-state unavailable");
      const state = await snapshot.json() as OfficialState;
      const version = state.state_version ?? 0;
      if (version >= latestVersionRef.current) {
        synchronizeRun(state);
        latestVersionRef.current = version;
        lastOfficialStateRef.current = state;
        setOfficialState(state);
        reconcilePresentation(version);
      }
      if (typeof state.sound_effects_enabled === "boolean") setSoundEffectsEnabled(state.sound_effects_enabled);
      if (typeof state.background_music_enabled === "boolean") setBackgroundMusicEnabled(state.background_music_enabled);
      if (state.movement_speed) setMovementSpeed(state.movement_speed);
      if (state.countdown_speed) setCountdownSpeed(state.countdown_speed);
      if (typeof state.hearts_per_match === "number") setHeartsRequired(state.hearts_per_match);
      setRealtimeStatus(realtimeDisplayStatus({ hasSnapshot: true, websocketSubscribed: false }));
    } catch {
      // A transient snapshot failure cannot undo an already accepted Start;
      // the realtime effect continues its authenticated reconnection path.
      setRealtimeStatus("connecting");
    }
    setScreen("arena");
  }

  async function repeatTournament() {
    const run = officialState?.run_id;
    if (!run || !organizerToken || repeatBusyRef.current || officialState?.status !== "completed") return;
    repeatBusyRef.current = true;
    setRepeatBusy(true);
    if (repeatCommandRef.current?.run !== run) repeatCommandRef.current = { run, key: crypto.randomUUID() };
    try {
      const response = await fetch(`/api/v1/tournaments/${encodeURIComponent(code)}/admin/repeat`, {
        method: "POST",
        headers: { "Content-Type": "application/json", Authorization: `Bearer ${organizerToken}`, "Idempotency-Key": repeatCommandRef.current.key },
        body: JSON.stringify({ expected_run_id: run }),
      });
      if (!response.ok) return reportRequestFailure(response);
      clearRequestFailure();
      const snapshot = await fetch(`/api/v1/tournaments/${encodeURIComponent(code)}/official-state`, { headers: { Authorization: `Bearer ${organizerToken}` } });
      if (!snapshot.ok) return reportRequestFailure(snapshot);
      const state = await snapshot.json() as OfficialState;
      if ((state.state_version ?? 0) >= latestVersionRef.current) {
        synchronizeRun(state);
        latestVersionRef.current = state.state_version ?? 0;
        lastOfficialStateRef.current = state;
        setOfficialState(state);
        reconcilePresentation(latestVersionRef.current);
      }
      setScreen("arena");
    } catch { reportRequestFailure(); }
    finally { repeatBusyRef.current = false; setRepeatBusy(false); }
  }

  function startAnimalRush() {
    if (tournamentStartedRef.current) return interruptForOfficialStart();
    clearAnimalRushTimer();
    setRushPrompt(randomAnimalRushMove());
    setRushScore(0);
    setRushStreak(0);
    setRushEndedStreak(0);
    setRushFeedback(null);
    setRushCorrectAnswer(null);
    setScreen("animal-rush");
  }

  function answerAnimalRush(answer: AnimalRushMove) {
    if (screen !== "animal-rush" || tournamentStartedRef.current) return;
    clearAnimalRushTimer();
    const result = resolveAnimalRushAnswer(rushPrompt, answer, {
      score: rushScore,
      streak: rushStreak,
      bestStreak: rushBestStreak,
    });
    if (!result.correct) {
      setRushEndedStreak(rushStreak);
      setRushCorrectAnswer(winningAnimalRushMove(rushPrompt));
      setRushFeedback("incorrect");
      setRushStreak(0);
      setScreen("animal-rush-result");
      return;
    }
    setRushScore(result.score);
    setRushStreak(result.streak);
    setRushBestStreak(result.bestStreak);
    setRushFeedback("correct");
    setRushCorrectAnswer(null);
    setRushPrompt(randomAnimalRushMove());
  }

  function returnFromAnimalRush() {
    clearAnimalRushTimer();
    setRushScore(0);
    setRushStreak(0);
    setRushEndedStreak(0);
    setRushFeedback(null);
    setRushCorrectAnswer(null);
    setScreen("waiting");
  }

  async function playTraining(move: "rock" | "paper" | "scissors") {
    const before = trainingState;
    const response = await fetch(guestTraining ? "/api/v1/training/guest/choice" : `/api/v1/tournaments/${encodeURIComponent(code)}/training/choice`, { method: "POST", headers: { "Content-Type": "application/json", ...(guestTrainingId ? { "X-Training-Session": guestTrainingId } : {}), ...(!guestTraining ? { Authorization: `Bearer ${playerToken}` } : {}) }, body: JSON.stringify(guestTraining ? { move, hearts_required: guestHearts ?? 1, strategy } : { move }) });
    if (!response.ok) return reportRequestFailure(response);
    const payload = await response.json();
    const nextState = payload.state as TrainingState;
    if (tournamentStartedRef.current) return;
    if (guestTraining) setGuestTrainingId(String(payload.training_id));
    setTrainingState(nextState);
    const lostHeart = (nextState.manual_hearts ?? 0) < (before?.manual_hearts ?? nextState.manual_hearts ?? 0) || (nextState.character_hearts ?? 0) < (before?.character_hearts ?? nextState.character_hearts ?? 0);
    if (lostHeart) audio?.effect("heart_lost");
    if (nextState.status === "completed") setScreen(guestTraining ? "guest-training-complete" : "training-complete");
    clearRequestFailure();
  }

  async function beginTraining(avatar: TrainingAvatar) {
    startTrainingAudio();
    resetTrainingChampionCue(trainingChampionCueRef);
    setTrainingAvatar(avatar);
    setTrainingState(null);
    const response = await fetch(`/api/v1/tournaments/${encodeURIComponent(code)}/training/reset`, { method: "POST", headers: { Authorization: `Bearer ${playerToken}` } });
    if (!response.ok) return reportRequestFailure(response);
    if (tournamentStartedRef.current) return;
    clearRequestFailure();
    setScreen("training");
  }

  function returnToWaiting() {
    setTrainingState(null);
    setTrainingAvatar(null);
    clearRequestFailure();
    setGuestTrainingId("");
    setGuestHearts(null);
    setHoveredGuestHearts(0);
    setScreen(guestTraining ? "guest-animal" : "waiting");
  }

  function beginGuestTraining(avatar: TrainingAvatar, selectedHearts: number) {
    resetTrainingChampionCue(trainingChampionCueRef);
    setTrainingAvatar(avatar);
    setGuestHearts(selectedHearts);
    setHoveredGuestHearts(0);
    setTrainingState(null);
    setGuestTrainingId("");
    clearRequestFailure();
    setScreen("guest-strategy");
  }

  function startGuestTraining() {
    if (!validStrategy || !trainingAvatar || !guestHearts) return reportRequestFailure();
    startTrainingAudio();
    resetTrainingChampionCue(trainingChampionCueRef);
    setTrainingState(null);
    setGuestTrainingId("");
    clearRequestFailure();
    setScreen("guest-training");
  }

  const arenaRounds = officialState
    ? [...officialState.completed_rounds, ...(officialState.current_round ? [officialState.current_round] : [])]
    : [];
  const arenaMatch = officialState?.current_round?.matches.find((match) => match.status === "active")
    ?? officialState?.current_round?.matches[0];
  const officialPlayer = (playerId: string | null | undefined) => officialState?.players.find((player) => player.player_id === playerId);
  const playerEmoji = (playerId: string | null | undefined) => animals.find((item) => item.id === officialPlayer(playerId)?.animal_id)?.emoji ?? "❔";

  return <main className="shell" dir={locale === "ar" ? "rtl" : "ltr"}>
    <audio ref={selectionAudioRef} className="animal-selection-audio" preload="auto" aria-hidden="true" />
    <header className="topbar">
      <div className="brand-stack">
        <div className="brand-row">
          <button className="back brand" onClick={() => setScreen("home")}>RPS: <b>ANIMAL</b> SHOWDOWN</button>
          <div className="player-audio-controls" role="group" aria-label={t("music")}>
            <button type="button" className="player-audio-toggle" aria-pressed={playerBackgroundMusicEnabled} onClick={() => updatePlayerAudioPreferences(playerSoundEffectsEnabled, !playerBackgroundMusicEnabled)}>
              <span aria-hidden="true">🎵</span><span>{t("music")}</span><b>{playerBackgroundMusicEnabled ? t("musicOn") : t("musicOff")}</b>
            </button>
            <button type="button" className="player-audio-toggle" aria-pressed={playerSoundEffectsEnabled} onClick={() => updatePlayerAudioPreferences(!playerSoundEffectsEnabled, playerBackgroundMusicEnabled)}>
              <span aria-hidden="true">🔊</span><span>{t("sound")}</span><b>{playerSoundEffectsEnabled ? t("audioOn") : t("audioOff")}</b>
            </button>
          </div>
        </div>
        <div className="locale-switcher" role="group" aria-label={u("language")}>
          {locales.map((item) => <button key={item} type="button" className="locale-choice" aria-pressed={locale === item} onClick={() => setLocale(item)}>
            <span className={`flag flag-${item}`} aria-hidden="true" />
            <span>{localeNames[item]}</span>
          </button>)}
        </div>
      </div>
      {screen !== "home" && <button type="button" className="return-home" onClick={() => setScreen("home")}>← {t("home")}</button>}
    </header>

    {screen === "home" && <section className="hero">
      <div>
        <span className="eyebrow"><span>{u("liveArena")}</span><span className="live-indicator" aria-hidden="true" /></span>
        <h1>RPS<br />ANIMAL<br />SHOWDOWN</h1>
        <div className="animal-showcase" role="img" aria-label={t("tagline")}>
          {animalShowcaseRows.map((row, rowIndex) => <div className="animal-row" key={rowIndex}>{row.map((emoji, emojiIndex) => <span key={`${rowIndex}-${emojiIndex}`}>{emoji}</span>)}</div>)}
        </div>
        <div className="cta-row">
          <button className="button home-action home-action-join" aria-label={homeActionAria("homeJoinAction")} onClick={() => setScreen("join")}>{homeActionLabel("homeJoinAction")}</button>
          <button className="button home-action home-action-create" aria-label={homeActionAria("homeCreateAction")} onClick={() => { clearRequestFailure(); setScreen("create"); }}>{homeActionLabel("homeCreateAction")}</button>
          <button className="button home-action home-action-training" aria-label={homeActionAria("homeTrainingAction")} onClick={() => { tournamentStartedRef.current = false; clearRequestFailure(); setTrainingState(null); setTrainingAvatar(null); setGuestTrainingId(""); setGuestHearts(null); setHoveredGuestHearts(0); setScreen("guest-animal"); }}>{homeActionLabel("homeTrainingAction")}</button>
        </div>
      </div>
      <aside className="sponsor">
        <small>{t("sponsored")}</small>
        <strong>Vitor Marchetti Craveiro</strong>
        <span className="sponsor-mark" aria-label={u("sponsorImage")} role="img" />
        <a className="button secondary" href="/patrocinar">{t("sponsor")}</a>
      </aside>
    </section>}

    {screen === "create" && <section>
      <h1 className="view-title">{t("createTitle")}</h1>
      <div className="panel form-grid">
        <label className="field">{t("capacity")}<input type="number" min="2" value={capacity} onChange={(event) => setCapacity(Math.max(2, Number(event.target.value) || 2))} /></label>
        <label className="field">{t("format")}<select value={matchFormat} onChange={(event) => setMatchFormat(Number(event.target.value) as MatchFormat)}><option value="1">{u("bestOf1")}</option><option value="3">{u("bestOf3")}</option><option value="5">{u("bestOf5")}</option><option value="7">{u("bestOf7")}</option></select></label>
        <label className="field">{t("movement")}<select value={movementSpeed} onChange={(event) => setMovementSpeed(event.target.value as PlaybackSpeed)}>{playbackSpeeds.map((speed) => <option key={speed.value} value={speed.value}>{u(speed.label)}</option>)}</select></label>
        <label className="field">{t("countdown")}<select value={countdownSpeed} onChange={(event) => setCountdownSpeed(event.target.value as PlaybackSpeed)}>{playbackSpeeds.map((speed) => <option key={speed.value} value={speed.value}>{u(speed.label)}</option>)}</select><small className="field-hint">{u("countdownSequence")}</small></label>
        <label className="audio-choice"><span>{t("sound")}</span><input type="checkbox" checked={soundEffectsEnabled} onChange={(event) => setSoundEffectsEnabled(event.target.checked)} /><b>{soundEffectsEnabled ? t("audioOn") : t("audioOff")}</b></label>
        <label className="audio-choice"><span>{t("music")}</span><input type="checkbox" checked={backgroundMusicEnabled} onChange={(event) => setBackgroundMusicEnabled(event.target.checked)} /><b>{backgroundMusicEnabled ? t("musicOn") : t("musicOff")}</b></label>
        <button className="button" disabled={createBusy} onClick={() => void createTournament()}>{t("create")}</button>
        {requestFailed && <p className="notice" role="alert">{requestFailureMessage}</p>}
      </div>
    </section>}

    {screen === "join" && <section>
      <h1 className="view-title">{t("joinTitle")}</h1>
      <div className="panel">
        <label className="field">{t("code")}<input value={code} onChange={(event) => { setCode(event.target.value); setPlayerToken(""); tournamentStartedRef.current = false; sessionStorage.removeItem("rps-player"); }} /></label>
        <label className="field">{t("name")}<input value={name} onChange={(event) => setName(event.target.value)} /></label>
        <div className="map-toolbar"><span>{u("mapHint")}</span><button type="button" className="map-zoom" onClick={() => setMapZoomed((current) => !current)}>{u(mapZoomed ? "mapReduce" : "mapEnlarge")}</button></div>
        <div className="world-viewport" role="region" aria-label={u("worldMap")} tabIndex={0}>
          <div className={`world ${mapZoomed ? "zoomed" : ""}`}>
            <Image className="world-base" src={`/maps/world-map-countries-${locale}.svg`} alt="" aria-hidden="true" width={1000} height={485} unoptimized />
            {animals.map((item) => <button key={item.id} type="button" style={{ left: `${item.x / 10}%`, top: `${item.y / 4.85}%` }} className={`animal-pin ${animal.id === item.id ? "selected" : ""}`} onClick={() => chooseAnimal(item)} aria-label={`${animalName(locale, item.id)} — ${regionName(locale, item.country)} — ${u(item.continent)}`} title={animalName(locale, item.id)}>{item.emoji}</button>)}
          </div>
        </div>
        <div className="animal-detail"><span className="emoji">{animal.emoji}</span><div><div className="animal-name-line"><b>{selectedAnimalName} <em className="scientific-name">({scientificName(animal.id)})</em></b><button type="button" className="animal-sound" onClick={narrateAnimal} aria-label={`${u("narrateAnimal")}: ${selectedAnimalName}`} title={u("narrateAnimal")}>🔊</button></div><small>{regionName(locale, animal.country)} · {u(animal.continent)}</small></div><button className="button" onClick={() => setScreen("strategy")}>{t("continue")}</button></div>
      </div>
    </section>}

    {screen === "guest-animal" && <section>
      <h1 className="view-title">{u("chooseTrainingAnimal")}</h1>
      <div className="panel">
        <div className="map-toolbar"><span>{u("mapHint")}</span><button type="button" className="map-zoom" onClick={() => setMapZoomed((current) => !current)}>{u(mapZoomed ? "mapReduce" : "mapEnlarge")}</button></div>
        <div className="world-viewport" role="region" aria-label={u("worldMap")} tabIndex={0}><div className={`world ${mapZoomed ? "zoomed" : ""}`}><Image className="world-base" src={`/maps/world-map-countries-${locale}.svg`} alt="" aria-hidden="true" width={1000} height={485} unoptimized />{animals.map((item) => <button key={item.id} type="button" style={{ left: `${item.x / 10}%`, top: `${item.y / 4.85}%` }} className={`animal-pin ${animal.id === item.id ? "selected" : ""}`} onClick={() => chooseAnimal(item)} aria-label={`${animalName(locale, item.id)} — ${regionName(locale, item.country)}`} title={animalName(locale, item.id)}>{item.emoji}</button>)}</div></div>
        <div className="animal-detail"><span className="emoji">{animal.emoji}</span><div><div className="animal-name-line"><b>{selectedAnimalName} <em className="scientific-name">({scientificName(animal.id)})</em></b><button type="button" className="animal-sound" onClick={narrateAnimal} aria-label={`${u("narrateAnimal")}: ${selectedAnimalName}`}>🔊</button></div><small>{regionName(locale, animal.country)} · {u(animal.continent)}</small></div><button className="button" onClick={() => setScreen("guest-training-avatar")}>{t("continue")}</button></div>
      </div>
    </section>}

    {(screen === "strategy" || screen === "guest-strategy") && <section>
      <h1 className="view-title">{t("strategy")}</h1>
      <div className="panel">
        <p className="muted">{u("strategyIntro")}</p>
        <div className="strategy-tabs">{strategyConditions.map((key) => <button key={key} className={condition === key ? "active" : ""} onClick={() => setCondition(key)}>{conditionLabels[locale][key]}</button>)}</div>
        <h3>{conditionLabels[locale][condition]}</h3>
        <label className="distribution">{u("rock")}<input type="number" min="0" max="100" value={distribution.rock} onChange={(event) => updateDistribution("rock", Number(event.target.value))} /></label>
        <label className="distribution">{u("paper")}<input type="number" min="0" max="100" value={distribution.paper} onChange={(event) => updateDistribution("paper", Number(event.target.value))} /></label>
        <label className="distribution">{u("scissors")}<input type="number" min="0" max="100" value={distribution.scissors} onChange={(event) => updateDistribution("scissors", Number(event.target.value))} /></label>
        <div className="toolbar strategy-actions"><button className="button secondary" onClick={randomize}>🎲 {u("random")}</button><button className="button secondary" onClick={randomizeAll}>🎲🎲 {u("randomAll")}</button></div>
        <p className={`total ${total === 100 ? "good" : "bad"}`}>{t("total")} {total}%</p>
        {requestFailed && <p className="notice" role="alert">{requestFailureMessage}</p>}
        <button disabled={!validStrategy} className="button" onClick={() => screen === "guest-strategy" ? startGuestTraining() : void readyForTournament()}>{screen === "guest-strategy" ? u("startTraining") : t("ready")}</button>
      </div>
    </section>}

    {screen === "waiting" && <section>
      <h1 className="view-title">{u("waitingTitle")}</h1>
      <div className="panel waiting-room"><p className="waiting-lead">{u("waitingOrganizer")}</p><ul className="waiting-checklist"><li>✓ {u("waitingRegistered")}</li><li>✓ {u("waitingReady")}</li><li>↻ {u("waitingNoRefresh")}</li><li>⚡ {u("waitingAutoStart")}</li></ul><p className="muted">{animal.emoji} {selectedAnimalName} · {name}</p>{requestFailed && <p className="notice" role="alert">{requestFailureMessage}</p>}<button className="button" onClick={startAnimalRush}>{u("playAnimalRush")}</button></div>
    </section>}

    {screen === "animal-rush" && <section className="rush-page">
      <h1 className="view-title">{u("animalRushTitle")}</h1>
      <div className="panel rush-panel">
        <div className="rush-player"><span>{animal.emoji}</span><b>{name || selectedAnimalName}</b></div>
        <p className="rush-instruction">{u("animalRushInstruction")}</p>
        <div className="rush-stats" aria-label={u("animalRushStats")}><span>{u("rushScore")}<b>{rushScore}</b></span><span>{u("rushStreak")}<b>{rushStreak}</b></span><span>{u("rushBestStreak")}<b>{rushBestStreak}</b></span></div>
        <div className="rush-prompt" aria-live="polite"><span>{animalRushEmoji[rushPrompt]}</span><b>{u(rushPrompt)}</b></div>
        <div className="rush-timer" aria-label={`${u("rushTime")}: ${Math.ceil(rushRoundMs / 1000)}`}><span key={`${rushPrompt}-${rushScore}`} style={{ animationDuration: `${rushRoundMs}ms` }} /></div>
        <p className={`rush-feedback ${rushFeedback === "correct" ? "correct" : ""}`} aria-live="polite">{rushFeedback === "correct" ? u("rushCorrect") : "\u00a0"}</p>
        <div className="rush-controls">{(["rock", "paper", "scissors"] as AnimalRushMove[]).map((move) => <button key={move} type="button" className="button secondary" onClick={() => answerAnimalRush(move)}><span>{animalRushEmoji[move]}</span>{u(move)}</button>)}</div>
      </div>
      <div className="training-back-row"><button className="button secondary" onClick={returnFromAnimalRush}>{u("returnWaiting")}</button></div>
    </section>}

    {screen === "animal-rush-result" && <section className="rush-page">
      <h1 className="view-title">{u("animalRushTitle")}</h1>
      <div className="panel rush-result">
        <span className="rush-result-animal">{animal.emoji}</span>
        <h2>{u("rushSequenceEnded")}</h2>
        <p className="notice">{u(rushFeedback === "timeout" ? "rushTimeout" : "rushIncorrect")}</p>
        {rushCorrectAnswer && <p className="rush-correct-answer">{u("rushCorrectAnswer")}: <b>{animalRushEmoji[rushCorrectAnswer]} {u(rushCorrectAnswer)}</b></p>}
        <div className="rush-stats"><span>{u("rushScore")}<b>{rushScore}</b></span><span>{u("rushStreak")}<b>{rushEndedStreak}</b></span><span>{u("rushBestStreak")}<b>{rushBestStreak}</b></span></div>
        <div className="rush-result-actions"><button className="button" onClick={startAnimalRush}>{u("rushPlayAgain")}</button><button className="button secondary" onClick={returnFromAnimalRush}>{u("returnWaiting")}</button></div>
      </div>
    </section>}

    {(screen === "training-avatar" || screen === "guest-training-avatar") && <section>
      <h1 className="view-title">{u("chooseTrainer")}</h1>
      <div className="panel">
        {screen === "guest-training-avatar" && trainingAvatar ? <div className="selected-trainer-card">
          <span className="selected-trainer-emoji" aria-label={u(trainingAvatar.label)} role="img">{trainingAvatar.emoji}</span>
          <div className="heart-picker" role="group" aria-label={u("chooseHearts")} onMouseLeave={() => setHoveredGuestHearts(0)}>
            {[1, 2, 3, 4, 5].map((count) => <button key={count} type="button" className={count <= (hoveredGuestHearts || guestHearts || 0) ? "active" : ""} aria-label={`${u("heartsCount")}: ${count}`} onMouseEnter={() => setHoveredGuestHearts(count)} onFocus={() => setHoveredGuestHearts(count)} onBlur={() => setHoveredGuestHearts(0)} onClick={() => beginGuestTraining(trainingAvatar, count)}>♥</button>)}
          </div>
        </div> : <div className="avatar-catalog">{trainingAvatars.map((avatar) => <button key={avatar.id} type="button" className="avatar-choice" aria-label={u(avatar.label)} title={u(avatar.label)} onClick={() => screen === "guest-training-avatar" ? (setTrainingAvatar(avatar), setGuestHearts(null), setHoveredGuestHearts(0)) : void beginTraining(avatar)}><span aria-hidden="true">{avatar.emoji}</span></button>)}</div>}
        {requestFailed && <p className="notice" role="alert">{requestFailureMessage}</p>}<button className="button secondary" onClick={() => screen === "guest-training-avatar" ? (setTrainingAvatar(null), setGuestHearts(null), setHoveredGuestHearts(0), setScreen("guest-animal")) : returnToWaiting()}>{screen === "guest-training-avatar" ? u("returnAnimalSelection") : u("returnWaiting")}</button>
      </div>
    </section>}

    {(screen === "training" || screen === "guest-training") && <section>
      <h1 className="view-title">{t("training")}</h1>
      <div className="panel training-panel"><div className="training-fighters"><div><span>{trainingAvatar?.emoji ?? "🙂"}</span><b>{u("trainingYou")}</b></div><span>{u("versus")}</span><div><span>{animal.emoji}</span><b>{guestTraining ? selectedAnimalName : `${u("tournamentAnimal")}: ${selectedAnimalName}`}</b></div></div><div className="training-hearts"><span>{u("trainingYou")}: {hearts(trainingState?.manual_hearts)}</span><span>{selectedAnimalName}: {hearts(trainingState?.character_hearts)}</span></div><div className="toolbar training-actions"><button className="button secondary training-move" onClick={() => void playTraining("rock")}>🗿 {u("rock")}</button><button className="button secondary training-move" onClick={() => void playTraining("paper")}>📄 {u("paper")}</button><button className="button secondary training-move" onClick={() => void playTraining("scissors")}>✂️ {u("scissors")}</button></div>{trainingState && <div className="training-result"><b>{u("trainingResult")}</b>{trainingState.rounds?.at(-1) && <p>{u("trainingRound")} {trainingState.rounds.at(-1)?.number}: {u(trainingState.rounds.at(-1)?.manual_move ?? "rock")} {u("versus")} {u(trainingState.rounds.at(-1)?.character_move ?? "rock")}</p>}</div>}{requestFailed && <p className="notice" role="alert">{requestFailureMessage}</p>}{!guestTraining && <button className="button secondary" onClick={returnToWaiting}>{u("returnWaiting")}</button>}</div>
      {guestTraining && <div className="training-back-row"><button className="button secondary" onClick={returnToWaiting}>{u("returnAnimalSelection")}</button></div>}
    </section>}

    {(screen === "training-complete" || screen === "guest-training-complete") && <section>
      <h1 className="view-title">{u("trainingComplete")}</h1>
      <div className="panel training-complete"><div className="training-champion">{trainingState?.winner === "manual_player" ? trainingAvatar?.emoji ?? "🙂" : animal.emoji}</div><h2>{u("trainingChampion")}</h2><p>{trainingState?.winner === "manual_player" ? u("trainingYou") : selectedAnimalName}</p><p className="muted">{trainingAvatar?.emoji ?? "🙂"} {u("versus")} {animal.emoji} · {hearts(trainingState?.manual_hearts)} {u("versus")} {hearts(trainingState?.character_hearts)}</p><button className="button" onClick={returnToWaiting}>{guestTraining ? u("returnAnimalSelection") : u("returnWaiting")}</button></div>
    </section>}

    {screen === "organizer" && <section>
      <h1 className="view-title">{t("organizer")}</h1>
<div className="panel"><p><b>{t("code")}:</b> {code}</p><p><b>{t("participants")}:</b> {participants.filter((participant) => !participant.removed).length}/{capacity}</p><div className="participants">{participants.map((participant) => <div className="participant" key={participant.player_id}><span>{participant.display_name} · {animals.find((item) => item.id === participant.animal_id)?.emoji ?? "❔"}</span><span className="status">{u(`participantStatus_${participant.membership_status ?? (participant.ready ? "ready" : "joined")}`)}</span></div>)}</div>{requestFailed && <p className="notice" role="alert">{requestFailureMessage}</p>}{officialState ? <button className="button" onClick={() => setScreen("arena")}>{t("arena")}</button> : <button className="button danger" disabled={participants.filter((participant) => participant.ready && !participant.removed).length < 2} onClick={() => void startTournament()}>{t("start")}</button>}</div>
    </section>}

    {screen === "arena" && <section>
      {officialStartNotice && <p className="notice success official-start-notice">{u("tournamentStartedNotice")}</p>}
      <h1 className="view-title">{t("arena")}</h1>
      <CinematicArena state={officialState} events={officialEvents} queue={presentationQueue} revision={presentationRevision} movement={movementSpeed} countdown={countdownSpeed} audio={audio} emoji={playerEmoji} u={u} realtime={realtimeStatus} podiumControls={organizerToken && officialState?.status === "completed" && <div className="actions"><button className="button primary" disabled={repeatBusy || !officialState.run_id} onClick={() => void repeatTournament()}>🔄 {u("repeatTournament")}</button><button className="button" onClick={() => setScreen("organizer")}>{u("backToPanel")}</button></div>} />
      {requestFailed && <p role="alert" className="notice">{requestFailureMessage}</p>}
    </section>}
  </main>;
}
