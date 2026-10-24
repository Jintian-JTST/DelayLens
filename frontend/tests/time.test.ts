import { test } from "node:test";
import assert from "node:assert/strict";
import { inputDate, inputISO, timeLabel } from "../src/time.ts";

test("UTC input remains unambiguous during the repeated UK hour", () => {
  assert.equal(inputISO("2026-10-25T01:15", "utc"), "2026-10-25T01:15:00.000Z");
  assert.equal(inputDate("2026-10-25T01:15:00Z", "utc"), "2026-10-25T01:15");
  assert.equal(timeLabel("2026-10-25T01:15:00Z", "utc"), "01:15");
});
test("changing a date input representation preserves its absolute instant", () => {
  const original = "2026-10-24T15:30:00.000Z";
  assert.equal(inputISO(inputDate(original, "local"), "local"), original);
});
