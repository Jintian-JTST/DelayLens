import { test } from "node:test";
import assert from "node:assert/strict";
import {
  askOffNotice,
  isSnapshotBasis,
  nextAskOffReason,
} from "../src/askAvailability.ts";

const snapshotBasis =
  "Based on 40 runs. Offline snapshot frozen 2026-10-24 20:25 UTC; not live data.";

test("snapshot basis text is detected; live basis is not", () => {
  assert.equal(isSnapshotBasis(snapshotBasis), true);
  assert.equal(isSnapshotBasis("Based on 40 runs."), false);
  assert.equal(isSnapshotBasis(undefined), false);
});

test("snapshot mode turns Ask off before any question and stays off", () => {
  const off = nextAskOffReason(null, { basis: snapshotBasis });
  assert.equal(off, "snapshot");
  assert.equal(
    nextAskOffReason(off, { basis: "Based on 40 runs." }),
    "snapshot",
  );
  assert.equal(nextAskOffReason(off, { askStatus: "ok" }), "snapshot");
  assert.match(askOffNotice(off), /offline snapshot mode/);
});

test("gemini_unavailable turns Ask off; a later working reply turns it back on", () => {
  const off = nextAskOffReason(null, { askStatus: "gemini_unavailable" });
  assert.equal(off, "gemini");
  assert.equal(nextAskOffReason(off, { basis: "Based on 40 runs." }), "gemini");
  assert.equal(nextAskOffReason(off, { askStatus: "ok" }), null);
  assert.match(askOffNotice(off), /unavailable/);
});

test("live basis and normal replies keep Ask on", () => {
  assert.equal(nextAskOffReason(null, { basis: "Based on 40 runs." }), null);
  assert.equal(nextAskOffReason(null, { askStatus: "unclear" }), null);
  assert.equal(askOffNotice(null), "");
});
