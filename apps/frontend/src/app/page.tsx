"use client";

import { useEffect, useState } from "react";
import Image from "next/image";
import { animalName, animalShowcaseRows, Locale, localeNames, locales, regionName, scientificName, text, uiText } from "../i18n/catalog";

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

type Screen = "home" | "create" | "join" | "strategy" | "waiting" | "training" | "organizer" | "arena";
type Distribution = { rock: number; paper: number; scissors: number };
type Participant = { player_id: string; display_name: string; animal_id: string; ready: boolean; strategy_locked: boolean };
type TrainingRound = { number: number; manual_move: string; character_move: string; manual_hearts: number; character_hearts: number };
type TrainingState = { manual_hearts?: number; character_hearts?: number; rounds?: TrainingRound[] };
type MatchFormat = 1 | 3 | 5 | 7;
type PlaybackSpeed = "0.5" | "1" | "2" | "4" | "8";
const playbackSpeeds: ReadonlyArray<{ value: PlaybackSpeed; label: string }> = [
  { value: "0.5", label: "speed05" },
  { value: "1", label: "speed1" },
  { value: "2", label: "speed2" },
  { value: "4", label: "speed4" },
  { value: "8", label: "speed8" },
];
const animalSoundProfiles: Record<string, { notes: number[]; wave: OscillatorType; duration: number }> = {
  eagle: { notes: [1340, 1660, 1980], wave: "sine", duration: 0.09 }, panda: { notes: [170, 145, 125], wave: "sawtooth", duration: 0.12 },
  kangaroo: { notes: [145, 110, 145], wave: "square", duration: 0.08 }, otter: { notes: [880, 1120, 1440], wave: "sine", duration: 0.08 },
  monkey: { notes: [640, 900, 720, 1080], wave: "square", duration: 0.07 }, rooster: { notes: [500, 740, 1080], wave: "sawtooth", duration: 0.12 },
  bull: { notes: [92, 78, 92], wave: "sawtooth", duration: 0.18 }, tiger: { notes: [118, 98, 84], wave: "sawtooth", duration: 0.18 },
  elephant: { notes: [72, 100, 144], wave: "sine", duration: 0.22 }, bear: { notes: [102, 88, 72], wave: "sawtooth", duration: 0.18 },
  octopus: { notes: [210, 180, 150], wave: "sine", duration: 0.13 }, llama: { notes: [390, 520, 390], wave: "square", duration: 0.1 },
  white_tailed_deer: { notes: [520, 640, 780], wave: "sine", duration: 0.11 }, camel: { notes: [115, 125, 108], wave: "sawtooth", duration: 0.16 },
  goat: { notes: [330, 480, 330], wave: "square", duration: 0.1 }, lizard: { notes: [310, 260, 220], wave: "sawtooth", duration: 0.1 },
  angora_cat: { notes: [430, 600, 720], wave: "sine", duration: 0.1 }, zebra: { notes: [260, 390, 520], wave: "square", duration: 0.1 },
  macaw: { notes: [880, 1320, 980], wave: "sawtooth", duration: 0.1 }, crane: { notes: [700, 920, 1160], wave: "sine", duration: 0.11 },
  lion: { notes: [94, 80, 68], wave: "sawtooth", duration: 0.2 }, penguin: { notes: [1040, 1320, 1040], wave: "sine", duration: 0.08 },
  gorilla: { notes: [78, 70, 62], wave: "square", duration: 0.2 }, hilsa: { notes: [620, 780, 930], wave: "sine", duration: 0.07 },
  horse: { notes: [250, 330, 440], wave: "sawtooth", duration: 0.11 }, shark: { notes: [150, 120, 90], wave: "sine", duration: 0.16 },
};

function playAnimalSound(animalId: string) {
  const profile = animalSoundProfiles[animalId];
  if (!profile) return;

  const audioContext = new window.AudioContext();
  const gain = audioContext.createGain();
  gain.connect(audioContext.destination);
  const start = audioContext.currentTime;
  gain.gain.setValueAtTime(0.0001, start);
  gain.gain.exponentialRampToValueAtTime(0.12, start + 0.02);

  profile.notes.forEach((note, index) => {
    const oscillator = audioContext.createOscillator();
    const noteStart = start + index * (profile.duration * 0.72);
    oscillator.type = profile.wave;
    oscillator.frequency.setValueAtTime(note, noteStart);
    oscillator.connect(gain);
    oscillator.start(noteStart);
    oscillator.stop(noteStart + profile.duration);
  });

  const end = start + profile.notes.length * (profile.duration * 0.72) + profile.duration;
  gain.gain.exponentialRampToValueAtTime(0.0001, end);
  window.setTimeout(() => void audioContext.close(), Math.ceil((end - start) * 1000) + 40);
}
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
  const [organizerToken, setOrganizerToken] = useState("");
  const [playerToken, setPlayerToken] = useState("");
  const [sessionRestored, setSessionRestored] = useState(false);
  const [participants, setParticipants] = useState<Participant[]>([]);
  const [requestFailed, setRequestFailed] = useState(false);
  const [trainingState, setTrainingState] = useState<TrainingState | null>(null);
  const t = (key: any) => text(locale, key);
  const u = (key: string) => uiText(locale, key);
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
  const hearts = (count = heartsRequired) => "❤️".repeat(count);

  useEffect(() => {
    const timer = window.setTimeout(() => {
      const savedScreen = sessionStorage.getItem("rps-screen");
      if (savedScreen && ["home", "create", "join", "strategy", "waiting", "training", "organizer", "arena"].includes(savedScreen)) setScreen(savedScreen as Screen);
      setCode(sessionStorage.getItem("rps-code") ?? "");
      setOrganizerToken(sessionStorage.getItem("rps-organizer") ?? "");
      setPlayerToken(sessionStorage.getItem("rps-player") ?? "");
      setSessionRestored(true);
    }, 0);
    return () => window.clearTimeout(timer);
  }, []);

  useEffect(() => {
    if (!sessionRestored) return;
    sessionStorage.setItem("rps-screen", screen);
    sessionStorage.setItem("rps-code", code);
  }, [code, screen, sessionRestored]);

  useEffect(() => {
    if (screen !== "organizer" || !code || !organizerToken) return;
    const loadParticipants = async () => {
      const response = await fetch(`/api/v1/tournaments/${encodeURIComponent(code)}/admin/participants`, { headers: { Authorization: `Bearer ${organizerToken}` } });
      if (!response.ok) return setRequestFailed(true);
      const payload = await response.json();
      setParticipants(Array.isArray(payload.participants) ? payload.participants : []);
    };
    void loadParticipants();
    const timer = window.setInterval(() => void loadParticipants(), 10_000);
    return () => window.clearInterval(timer);
  }, [code, organizerToken, screen]);

  useEffect(() => {
    if ((screen !== "waiting" && screen !== "arena") || !code || !playerToken) return;
    const refreshStatus = async () => {
      const response = await fetch(`/api/v1/tournaments/${encodeURIComponent(code)}/players/me`, { headers: { Authorization: `Bearer ${playerToken}` } });
      if (!response.ok) return setRequestFailed(true);
      const payload = await response.json();
      if (typeof payload.hearts_required === "number") setHeartsRequired(payload.hearts_required);
      if (typeof payload.movement_speed === "string") setMovementSpeed(payload.movement_speed as PlaybackSpeed);
      if (typeof payload.countdown_speed === "string") setCountdownSpeed(payload.countdown_speed as PlaybackSpeed);
      if (payload.tournament_started === true) setScreen("arena");
    };
    void refreshStatus();
    const timer = window.setInterval(() => void refreshStatus(), 10_000);
    return () => window.clearInterval(timer);
  }, [code, playerToken, screen]);

  async function createTournament() {
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
    if (!response.ok) return;
    const tournament = await response.json();
    setCode(tournament.tournament_code);
    setOrganizerToken(tournament.organizer_access_token);
    setHeartsRequired(tournament.hearts_required);
    sessionStorage.setItem("rps-organizer", tournament.organizer_access_token);
    setScreen("organizer");
  }

  async function readyForTournament() {
    if (!code.trim() || !name.trim() || !validStrategy) return setRequestFailed(true);
    let capability = playerToken;
    if (!capability) {
      const joined = await fetch("/api/v1/tournaments/join", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ tournament_code: code, display_name: name, animal_id: animal.id }) });
      if (!joined.ok) return setRequestFailed(true);
      const payload = await joined.json();
      capability = payload.player_access_token;
      if (typeof payload.hearts_required === "number") setHeartsRequired(payload.hearts_required);
      if (typeof payload.movement_speed === "string") setMovementSpeed(payload.movement_speed as PlaybackSpeed);
      if (typeof payload.countdown_speed === "string") setCountdownSpeed(payload.countdown_speed as PlaybackSpeed);
      setPlayerToken(capability);
      sessionStorage.setItem("rps-player", capability);
    }
    const headers = { "Content-Type": "application/json", Authorization: `Bearer ${capability}` };
    const strategyResponse = await fetch(`/api/v1/tournaments/${encodeURIComponent(code)}/players/me/strategy`, { method: "PUT", headers, body: JSON.stringify(strategy) });
    if (!strategyResponse.ok) return setRequestFailed(true);
    const readyResponse = await fetch(`/api/v1/tournaments/${encodeURIComponent(code)}/players/me/ready`, { method: "POST", headers, body: "{}" });
    if (!readyResponse.ok) return setRequestFailed(true);
    setRequestFailed(false);
    setScreen("waiting");
  }

  async function startTournament() {
    const response = await fetch(`/api/v1/tournaments/${encodeURIComponent(code)}/admin/start`, { method: "POST", headers: { "Content-Type": "application/json", Authorization: `Bearer ${organizerToken}`, "Idempotency-Key": crypto.randomUUID() }, body: "{}" });
    if (!response.ok) return setRequestFailed(true);
    setRequestFailed(false);
    setScreen("arena");
  }

  async function playTraining(move: "rock" | "paper" | "scissors") {
    const response = await fetch(`/api/v1/tournaments/${encodeURIComponent(code)}/training/choice`, { method: "POST", headers: { "Content-Type": "application/json", Authorization: `Bearer ${playerToken}` }, body: JSON.stringify({ move }) });
    if (!response.ok) return setRequestFailed(true);
    const payload = await response.json();
    setTrainingState(payload.state as TrainingState);
    setRequestFailed(false);
  }

  return <main className="shell" dir={locale === "ar" ? "rtl" : "ltr"}>
    <header className="topbar">
      <div className="brand-stack">
        <button className="back brand" onClick={() => setScreen("home")}>RPS: <b>ANIMAL</b> SHOWDOWN</button>
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
        <span className="eyebrow">{u("liveArena")}</span>
        <h1>RPS<br />ANIMAL<br />SHOWDOWN</h1>
        <div className="animal-showcase" role="img" aria-label={t("tagline")}>
          {animalShowcaseRows.map((row, rowIndex) => <div className="animal-row" key={rowIndex}>{row.map((emoji, emojiIndex) => <span key={`${rowIndex}-${emojiIndex}`}>{emoji}</span>)}</div>)}
        </div>
        <div className="cta-row">
          <button className="button" onClick={() => setScreen("join")}>{t("join")}</button>
          <button className="button secondary" onClick={() => setScreen("create")}>{t("create")}</button>
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
        <label className="audio-choice"><span>{t("music")}</span><input type="checkbox" checked={backgroundMusicEnabled} onChange={(event) => setBackgroundMusicEnabled(event.target.checked)} /><b>{backgroundMusicEnabled ? t("audioOn") : t("audioOff")}</b></label>
        <button className="button" onClick={createTournament}>{t("create")}</button>
      </div>
    </section>}

    {screen === "join" && <section>
      <h1 className="view-title">{t("joinTitle")}</h1>
      <div className="panel">
        <label className="field">{t("code")}<input value={code} onChange={(event) => setCode(event.target.value)} /></label>
        <label className="field">{t("name")}<input value={name} onChange={(event) => setName(event.target.value)} /></label>
        <div className="map-toolbar"><span>{u("mapHint")}</span><button type="button" className="map-zoom" onClick={() => setMapZoomed((current) => !current)}>{u(mapZoomed ? "mapReduce" : "mapEnlarge")}</button></div>
        <div className="world-viewport" role="region" aria-label={u("worldMap")} tabIndex={0}>
          <div className={`world ${mapZoomed ? "zoomed" : ""}`}>
            <Image className="world-base" src={`/maps/world-map-countries-${locale}.svg`} alt="" aria-hidden="true" width={1000} height={485} unoptimized />
            {animals.map((item) => <button key={item.id} type="button" style={{ left: `${item.x / 10}%`, top: `${item.y / 4.85}%` }} className={`animal-pin ${animal.id === item.id ? "selected" : ""}`} onClick={() => setAnimal(item)} aria-label={`${animalName(locale, item.id)} — ${regionName(locale, item.country)} — ${u(item.continent)}`} title={animalName(locale, item.id)}>{item.emoji}</button>)}
          </div>
        </div>
        <div className="animal-detail"><span className="emoji">{animal.emoji}</span><div><div className="animal-name-line"><b>{selectedAnimalName} <em className="scientific-name">({scientificName(animal.id)})</em></b><button type="button" className="animal-sound" onClick={() => playAnimalSound(animal.id)} aria-label={`${u("listenAnimalSound")}: ${selectedAnimalName}`} title={u("listenAnimalSound")}>🔊</button></div><small>{regionName(locale, animal.country)} · {u(animal.continent)}</small></div><button className="button" onClick={() => setScreen("strategy")}>{t("continue")}</button></div>
      </div>
    </section>}

    {screen === "strategy" && <section>
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
        {requestFailed && <p className="notice">{t("network")}</p>}
        <button disabled={!validStrategy} className="button" onClick={readyForTournament}>{t("ready")}</button>
      </div>
    </section>}

    {screen === "waiting" && <section>
      <h1 className="view-title">{t("waiting")}</h1>
      <div className="panel"><p className="muted">{selectedAnimalName} · {name}</p>{requestFailed && <p className="notice">{t("network")}</p>}<button className="button" onClick={() => setScreen("training")}>{t("training")}</button></div>
    </section>}

    {screen === "training" && <section>
      <h1 className="view-title">{t("training")}</h1>
      <div className="panel"><div className="toolbar"><button className="button secondary" onClick={() => void playTraining("rock")}>🪨 {u("rock")}</button><button className="button secondary" onClick={() => void playTraining("paper")}>📄 {u("paper")}</button><button className="button secondary" onClick={() => void playTraining("scissors")}>✂️ {u("scissors")}</button></div>{trainingState && <div className="training-result"><b>{u("trainingResult")}</b><p>{u("trainingYou")}: {hearts(trainingState.manual_hearts)} · {u("trainingCharacter")}: {hearts(trainingState.character_hearts)}</p>{trainingState.rounds?.at(-1) && <p>{u("trainingRound")} {trainingState.rounds.at(-1)?.number}: {trainingState.rounds.at(-1)?.manual_move} {u("versus")} {trainingState.rounds.at(-1)?.character_move}</p>}</div>}{requestFailed && <p className="notice">{t("network")}</p>}<button className="button secondary" onClick={() => setScreen("waiting")}>{t("waiting")}</button></div>
    </section>}

    {screen === "organizer" && <section>
      <h1 className="view-title">{t("organizer")}</h1>
      <div className="panel"><p><b>{t("code")}:</b> {code}</p><p><b>{t("participants")}:</b> {participants.length}/{capacity}</p><div className="participants">{participants.map((participant) => <div className="participant" key={participant.player_id}><span>{participant.display_name} · {animals.find((item) => item.id === participant.animal_id)?.emoji ?? "❔"}</span><span className="status">{participant.ready ? t("ready") : t("waiting")}</span></div>)}</div>{requestFailed && <p className="notice">{t("network")}</p>}<button className="button danger" disabled={participants.filter((participant) => participant.ready).length < 2} onClick={() => void startTournament()}>{t("start")}</button></div>
    </section>}

    {screen === "arena" && <section>
      <h1 className="view-title">{t("arena")}</h1>
      <div className="arena">
        <div className="card battle"><div className="fighters">{animal.emoji} <span>{u("versus")}<br />{hearts()}</span> 🐯</div><p>{t("waiting")}</p></div>
        <div className="card"><h3>{t("bracket")}</h3>{participants.length ? participants.map((participant) => <p key={participant.player_id}>{animals.find((item) => item.id === participant.animal_id)?.emoji ?? "❔"} {participant.display_name}</p>) : <><p>{animal.emoji} {name || u("player")}</p><p>🐯 {u("challenger")}</p></>}</div>
        <div className="card"><h3>{t("events")}</h3><p className="event">{selectedAnimalName} {u("readySuffix")}</p><p className="event">{t("waiting")}</p><p className="event">{t("movement")}: {u(playbackSpeeds.find((speed) => speed.value === movementSpeed)?.label ?? "speed1")}</p><p className="event">{t("countdown")}: {u(playbackSpeeds.find((speed) => speed.value === countdownSpeed)?.label ?? "speed1")} · {u("countdownSequence")}</p></div>
      </div>
    </section>}
  </main>;
}
