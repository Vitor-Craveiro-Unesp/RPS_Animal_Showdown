// Presentation-only audio. Every source below is a file selected locally by the owner.
export const AUDIO_ASSETS = Object.freeze({
  animals: Object.freeze({
    eagle: '/audio/animals/A_eagle.mp3', panda: '/audio/animals/A_panda.mp3', kangaroo: '/audio/animals/A_kangaroo.mp3',
    otter: '/audio/animals/A_otter.mp3', monkey: '/audio/animals/A_japonese-macaque.mp3', rooster: '/audio/animals/A_rooster.mp3',
    bull: '/audio/animals/A_bull.mp3', tiger: '/audio/animals/A_tiger.mp3', elephant: '/audio/animals/A_elephant.mp3',
    bear: '/audio/animals/A_bear.mp3', octopus: '/audio/animals/A_octopus.mp3', llama: '/audio/animals/A_llama.mp3',
    white_tailed_deer: '/audio/animals/A_deer.mp3', camel: '/audio/animals/A_camel.mp3', goat: '/audio/animals/A_goat.mp3',
    lizard: '/audio/animals/A_komodo-dragon.mp3', angora_cat: '/audio/animals/A_cat.mp3', zebra: '/audio/animals/A_zebra.mp3',
    macaw: '/audio/animals/A_macaw.mp3', crane: '/audio/animals/A_crowned-crane.mp3', lion: '/audio/animals/A_lion.mp3',
    penguin: '/audio/animals/A_pinguin.mp3', gorilla: '/audio/animals/A_gorilla.mp3', hilsa: '/audio/animals/A-hilsa.mp3',
    horse: '/audio/animals/A_horse.mp3', shark: '/audio/animals/A_shark.mp3', zombie: '/audio/animals/A_zumbie.mp3',
  }),
  effects: Object.freeze({
    countdown: '/audio/effects/countdown_beep.mp3', heart_lost: '/audio/effects/heart_break.mp3',
    tie: '/audio/effects/tie.mp3', champion: '/audio/effects/champion.mp3', podium: '/audio/effects/podium.mp3',
  }),
  background: '/audio/background/background.mp3',
});

// Channels are intentionally exclusive: a new animal/effect replaces the prior one.
export class AudioManager {
  // The organizer control defaults to effects enabled. Starting with that same
  // value also makes an animal click safe during the first client hydration;
  // configure(false, ...) immediately silences it for an official OFF setting.
  constructor(host) { this.host = host; this.channels = new Map(); this.effects = true; this.music = false; this.celebrating = false; this.unlocked = false; }
  unlock() { this.unlocked = true; return Boolean(this.host.Audio || this.host.document?.createElement); }
  make(source, loop = false, volume = .5) {
    if (!this.host.Audio && !this.host.document?.createElement) return null;
    try {
      // A mounted media element is more reliable than a detached Audio object in
      // restrictive mobile/browser autoplay implementations, while still using
      // the same local source and bounded channel lifecycle.
      const audio = this.host.document?.createElement?.('audio') ?? new this.host.Audio(source);
      audio.src = source;
      audio.preload = 'auto'; audio.loop = loop; audio.volume = volume; audio.muted = false; audio.playsInline = true;
      audio.setAttribute?.('aria-hidden', 'true'); audio.classList?.add('audio-channel');
      if (audio.parentNode == null) this.host.document?.body?.appendChild?.(audio);
      return audio;
    } catch { return null; }
  }
  stop(channel) {
    const audio = this.channels.get(channel); if (!audio) return;
    try { audio.onended = null; audio.pause?.(); audio.currentTime = 0; audio.remove?.(); } catch {}
    this.channels.delete(channel);
  }
  play(channel, source, { loop = false, volume = .5 } = {}) {
    this.stop(channel);
    const audio = this.make(source, loop, volume); if (!audio) return false;
    this.channels.set(channel, audio);
    if (!loop) audio.onended = () => { if (this.channels.get(channel) === audio) this.channels.delete(channel); };
    try { void audio.play?.().catch(() => {}); } catch {}
    return true;
  }
  configure(effects, music) {
    this.effects = Boolean(effects);
    if (!this.effects) { this.stop('effect'); this.stop('animal'); }
    this.music = Boolean(music);
    if (!this.music) { this.stop('background'); return; }
    const current = this.channels.get('background');
    if (!current || current.src?.endsWith(AUDIO_ASSETS.background) === false) this.play('background', AUDIO_ASSETS.background, { loop: true, volume: .24 });
  }
  effect(kind) { const source = AUDIO_ASSETS.effects[kind]; return Boolean(this.effects && source && this.play('effect', source, { volume: .55 })); }
  animal(animalId, zombie = false) { this.cancelSpeech(); const source = zombie ? AUDIO_ASSETS.animals.zombie : AUDIO_ASSETS.animals[animalId]; return Boolean(this.effects && source && this.play('animal', source, { volume: .65 })); }
  winner(animalId, zombie = false) { return this.animal(animalId, zombie); }
  resetRun() { const effects = this.effects, music = this.music; this.stopAll(); this.configure(effects, music); }
  cancelSpeech() { this.host.speechSynthesis?.cancel?.(); }
  narrate(common, scientific, locale) {
    this.stop('animal'); this.cancelSpeech();
    if (!this.host.speechSynthesis || !this.host.SpeechSynthesisUtterance) return false;
    try {
      const speech = new this.host.SpeechSynthesisUtterance(`${common}. ${scientific}.`);
      speech.lang = { en: 'en-US', ar: 'ar-SA' }[locale] ?? locale;
      const voices = this.host.speechSynthesis.getVoices?.() ?? [];
      speech.voice = voices.find(voice => voice.lang === speech.lang) ?? voices.find(voice => voice.lang?.split('-')[0] === speech.lang.split('-')[0]) ?? null;
      this.host.speechSynthesis.speak(speech); return true;
    } catch { return false; }
  }
  stopAll() { for (const channel of [...this.channels.keys()]) this.stop(channel); this.cancelSpeech(); this.celebrating = false; }
  dispose() { this.stopAll(); }
}
