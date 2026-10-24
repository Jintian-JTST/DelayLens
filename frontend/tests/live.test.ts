import { test } from "node:test";
import assert from "node:assert/strict";
import { isOfflineSnapshot, OFFLINE_LIVE_MESSAGE } from "../src/live.ts";

test("snapshot-mode basis is detected as offline", () => {
  assert.equal(
    isOfflineSnapshot(
      "42 vehicle-run segments. Offline snapshot frozen 2026-10-24 20:25 UTC; not live data.",
    ),
    true,
  );
});

test("live database basis and missing basis are not offline", () => {
  assert.equal(isOfflineSnapshot("42 vehicle-run segments from live polls."), false);
  assert.equal(isOfflineSnapshot(""), false);
  assert.equal(isOfflineSnapshot(undefined), false);
});

test("offline message does not prompt a refresh", () => {
  assert.doesNotMatch(OFFLINE_LIVE_MESSAGE, /refresh/i);
});
