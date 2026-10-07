import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import { AudioManager } from "./audio-manager.mjs";

test("every page visit begins with music and sound effects enabled", () => {
  const page = readFileSync(new URL("./page.tsx", import.meta.url), "utf8");

  assert.match(page, /const \[playerSoundEffectsEnabled, setPlayerSoundEffectsEnabled\] = useState\(true\)/);
  assert.match(page, /const \[playerBackgroundMusicEnabled, setPlayerBackgroundMusicEnabled\] = useState\(true\)/);
  assert.doesNotMatch(page, /savedAudioPreference|localStorage\.setItem\("rps-player-(?:sound-effects|background-music)/);
});

test("background music retries on the first gesture after autoplay is blocked", async () => {
  let plays = 0;
  const host = {
    document: {
      body: { appendChild() {} },
      createElement() {
        return {
          classList: { add() {} }, setAttribute() {}, pause() {}, remove() {},
          play() { plays += 1; return plays === 1 ? Promise.reject(new Error("autoplay blocked")) : Promise.resolve(); },
        };
      },
    },
  };
  const manager = new AudioManager(host);
  manager.configure(true, true);
  await Promise.resolve();
  assert.equal(manager.channels.has("background"), false);
  manager.unlock();
  assert.equal(plays, 2);
  assert.equal(manager.channels.has("background"), true);
  manager.dispose();
});
