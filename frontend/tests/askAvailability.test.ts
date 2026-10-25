import { test } from "node:test";
import assert from "node:assert/strict";
import {
  askOffFromHealth,
  askOffNotice,
  askPlaceholder,
  nextAskOffReason,
} from "../src/askAvailability.ts";

test("health ask_available drives the initial Ask state, including snapshot mode", () => {
  // Snapshot mode is not an input any more: only the server's key decides.
  assert.equal(askOffFromHealth({ ask_available: true }), null);
  assert.equal(askOffFromHealth({ ask_available: false }), "no_key");
});

test("a failed health check (network error or non-200) turns Ask off as unchecked", () => {
  // App passes null when api.health() rejects, including ApiError for non-200.
  assert.equal(askOffFromHealth(null), "unchecked");
  assert.equal(askOffFromHealth(undefined), "unchecked");
  assert.match(askOffNotice("unchecked"), /could not check/);
  assert.match(askPlaceholder("unchecked"), /could not be checked/);
});

test("an older backend without the flag is treated as unchecked, not connected", () => {
  assert.equal(askOffFromHealth({}), "unchecked");
});

test("no notice or placeholder claims Gemini is connected or verified", () => {
  for (const reason of ["no_key", "unchecked", "gemini", null] as const) {
    const text = `${askOffNotice(reason)} ${askPlaceholder(reason)}`;
    assert.doesNotMatch(text, /connected to Gemini|Gemini (is )?(connected|verified|ready)/i);
  }
});

test("no_key is sticky and explains the Gemini key requirement", () => {
  assert.equal(nextAskOffReason("no_key", "ok"), "no_key");
  assert.equal(nextAskOffReason("no_key", undefined), "no_key");
  assert.equal(askOffFromHealth({ ask_available: false }), "no_key");
  assert.match(askOffNotice("no_key"), /Gemini API key on the server/);
  assert.match(askPlaceholder("no_key"), /Gemini key/);
});

test("unchecked is sticky until the health check is retried", () => {
  assert.equal(nextAskOffReason("unchecked", "ok"), "unchecked");
});

test("gemini_unavailable turns Ask off; a later working reply turns it back on", () => {
  const off = nextAskOffReason(null, "gemini_unavailable");
  assert.equal(off, "gemini");
  assert.equal(nextAskOffReason(off, undefined), "gemini");
  assert.equal(nextAskOffReason(off, "ok"), null);
  assert.match(askOffNotice(off), /could not reach Gemini/);
});

test("normal replies keep Ask on", () => {
  assert.equal(nextAskOffReason(null, "unclear"), null);
  assert.equal(nextAskOffReason(null, "unsupported_route"), null);
  assert.equal(askOffNotice(null), "");
  assert.doesNotMatch(askPlaceholder(null), /unavailable|Gemini/);
});
