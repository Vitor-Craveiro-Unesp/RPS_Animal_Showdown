import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

import { realtimeDisplayStatus, shouldPollOfficialSnapshot } from "./realtime-status.mjs";

test("an official snapshot resolves the organizer's connecting state without claiming a WebSocket subscription", () => {
  assert.equal(realtimeDisplayStatus({ hasSnapshot: false, websocketSubscribed: false }), "connecting");
  assert.equal(realtimeDisplayStatus({ hasSnapshot: true, websocketSubscribed: false }), "snapshot");
  assert.equal(realtimeDisplayStatus({ hasSnapshot: true, websocketSubscribed: true }), "live");
});

test("snapshot synchronization and fallback both keep the official state fresh", () => {
  assert.equal(shouldPollOfficialSnapshot("snapshot"), true);
  assert.equal(shouldPollOfficialSnapshot("fallback"), true);
  assert.equal(shouldPollOfficialSnapshot("live"), false);
  assert.equal(shouldPollOfficialSnapshot("connecting"), false);
});

test("snapshot status is localized for every supported interface", () => {
  const catalog = readFileSync(new URL("../i18n/catalog.ts", import.meta.url), "utf8");
  for (const copy of ["snapshot:\"Sincronizado\"", "snapshot:\"Synchronized\"", "snapshot:\"已同步\"", "snapshot:\"تمت المزامنة\""]) {
    assert.ok(catalog.includes(copy));
  }
});
