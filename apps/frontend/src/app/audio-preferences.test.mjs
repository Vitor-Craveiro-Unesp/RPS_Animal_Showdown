import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

test("new players begin with music muted and sound effects enabled", () => {
  const page = readFileSync(new URL("./page.tsx", import.meta.url), "utf8");

  assert.match(page, /const \[playerSoundEffectsEnabled, setPlayerSoundEffectsEnabled\] = useState\(true\)/);
  assert.match(page, /const \[playerBackgroundMusicEnabled, setPlayerBackgroundMusicEnabled\] = useState\(false\)/);
  assert.match(page, /savedAudioPreference\("rps-player-sound-effects", true\)/);
  assert.match(page, /savedAudioPreference\("rps-player-background-music-v2", false\)/);
});
