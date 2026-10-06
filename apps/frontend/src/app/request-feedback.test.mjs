import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

import { requestFeedbackKind } from "./request-feedback.mjs";

test("HTTP 429 receives the localized rate-limit feedback category", () => {
  assert.equal(requestFeedbackKind(429), "rateLimited");
});

test("other failures retain the generic connection feedback category", () => {
  assert.equal(requestFeedbackKind(400), "network");
  assert.equal(requestFeedbackKind(500), "network");
  assert.equal(requestFeedbackKind(undefined), "network");
});

test("rate-limit feedback is localized for every public locale", () => {
  const catalog = readFileSync(new URL("../i18n/catalog.ts", import.meta.url), "utf8");
  for (const copy of [
    "Você está fazendo muitas tentativas",
    "You are making too many attempts",
    "短时间内尝试次数过多",
    "تجري محاولات كثيرة",
  ]) assert.ok(catalog.includes(copy));
});
