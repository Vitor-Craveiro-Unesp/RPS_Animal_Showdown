"use client";

import { useState } from "react";
import Image from "next/image";
import { animalName, animalShowcaseRows, Locale, localeNames, locales, regionName, text, uiText } from "../i18n/catalog";

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

type Screen = "home" | "create" | "join" | "strategy" | "waiting" | "organizer" | "arena";
type Distribution = { rock: number; paper: number; scissors: number };
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
  const t = (key: any) => text(locale, key);
  const u = (key: string) => uiText(locale, key);
  const distribution = strategy[condition];
  const total = distribution.rock + distribution.paper + distribution.scissors;
  const completed = strategyConditions.filter((key) => strategy[key].rock + strategy[key].paper + strategy[key].scissors === 100).length;
  const validStrategy = completed === strategyConditions.length;
  const updateDistribution = (move: keyof Distribution, value: number) => setStrategy((current) => ({ ...current, [condition]: { ...current[condition], [move]: value } }));
  const copyToAll = () => setStrategy(Object.fromEntries(strategyConditions.map((key) => [key, { ...distribution }])));
  const randomize = () => setStrategy(Object.fromEntries(strategyConditions.map((key) => { const rock = Math.floor(Math.random() * 101); const paper = Math.floor(Math.random() * (101 - rock)); return [key, { rock, paper, scissors: 100 - rock - paper }]; })));
  const selectedAnimalName = animalName(locale, animal.id);

  async function createTournament() {
    const response = await fetch("/api/v1/tournaments", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ capacity: 8, hearts_required: 2 }),
    });
    if (!response.ok) return;
    const tournament = await response.json();
    setCode(tournament.tournament_code);
    sessionStorage.setItem("rps-organizer", tournament.organizer_access_token);
    setScreen("organizer");
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
        <label className="field">{t("capacity")}<input type="number" min="2" defaultValue="8" /></label>
        <label className="field">{t("format")}<select><option>{u("bestOf3")}</option><option>{u("bestOf1")}</option><option>{u("bestOf5")}</option></select></label>
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
        <div className="animal-detail"><span className="emoji">{animal.emoji}</span><div><b>{selectedAnimalName}</b><small>{regionName(locale, animal.country)} · {u(animal.continent)}</small></div><button className="button" onClick={() => setScreen("strategy")}>{t("continue")}</button></div>
      </div>
    </section>}

    {screen === "strategy" && <section>
      <h1 className="view-title">{t("strategy")}</h1>
      <div className="panel">
        <p className="muted">{locale === "pt-BR" ? "Você define como seu personagem escolhe Pedra, Papel ou Tesoura após cada resultado." : locale === "en" ? "Set how your character chooses Rock, Paper or Scissors after each result." : locale === "zh-CN" ? "设定你的角色在每种结果后如何选择石头、布或剪刀。" : "حدّد كيف يختار شخصك حجرًا أو ورقًا أو مقصًا بعد كل نتيجة."}</p>
        <div className="strategy-tabs">{strategyConditions.map((key) => <button key={key} className={condition === key ? "active" : ""} onClick={() => setCondition(key)}>{conditionLabels[locale][key]}</button>)}</div>
        <h3>{conditionLabels[locale][condition]}</h3>
        <label className="distribution">{u("rock")}<input type="number" min="0" max="100" value={distribution.rock} onChange={(event) => updateDistribution("rock", Number(event.target.value))} /></label>
        <label className="distribution">{u("paper")}<input type="number" min="0" max="100" value={distribution.paper} onChange={(event) => updateDistribution("paper", Number(event.target.value))} /></label>
        <label className="distribution">{u("scissors")}<input type="number" min="0" max="100" value={distribution.scissors} onChange={(event) => updateDistribution("scissors", Number(event.target.value))} /></label>
        <div className="toolbar strategy-actions"><button className="button secondary" onClick={randomize}>🎲 {locale === "pt-BR" ? "Aleatória" : locale === "en" ? "Random" : locale === "zh-CN" ? "随机" : "عشوائي"}</button><button className="button secondary" onClick={copyToAll}>{locale === "pt-BR" ? "Aplicar a todas" : locale === "en" ? "Apply to all" : locale === "zh-CN" ? "应用到全部" : "تطبيق على الكل"}</button></div>
        <p className={`total ${total === 100 ? "good" : "bad"}`}>{t("total")} {total}%</p>
        <button disabled={!validStrategy} className="button" onClick={() => setScreen("waiting")}>{t("ready")}</button>
      </div>
    </section>}

    {["waiting", "organizer", "arena"].includes(screen) && <section>
      <h1 className="view-title">{screen === "organizer" ? t("organizer") : t("waiting")}</h1>
      <div className="arena">
        <div className="card battle"><div className="fighters">{animal.emoji} <span>{u("versus")}<br />❤️❤️</span> 🐯</div><p>{t("waiting")}</p></div>
        <div className="card"><h3>{t("bracket")}</h3><p>{animal.emoji} {name || u("player")}</p><p>🐯 {u("challenger")}</p></div>
        <div className="card"><h3>{t("events")}</h3><p className="event">{selectedAnimalName} {u("readySuffix")}</p><p className="event">{t("waiting")}</p></div>
      </div>
      <button className="button danger" onClick={() => setScreen("arena")}>{screen === "organizer" ? t("start") : t("training")}</button>
    </section>}
  </main>;
}
