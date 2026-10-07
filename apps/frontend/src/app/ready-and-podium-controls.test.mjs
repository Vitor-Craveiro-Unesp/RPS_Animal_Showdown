import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

test("ready submission is single-flight and the completed podium cannot repeat a tournament", () => {
  const page = readFileSync(new URL("./page.tsx", import.meta.url), "utf8");

  assert.match(page, /const readyBusyRef = useRef\(false\)/);
  assert.match(page, /if \(readyBusyRef\.current\) return/);
  assert.match(page, /readyBusyRef\.current = true/);
  assert.match(page, /readyBusyRef\.current = false/);
  assert.match(page, /disabled=\{!validStrategy \|\| \(screen !== "guest-strategy" && readyBusy\)\}/);
  assert.doesNotMatch(page, /repeatTournament/);
  assert.doesNotMatch(page, /\/admin\/repeat/);
});
