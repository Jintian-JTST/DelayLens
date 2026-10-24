import assert from "node:assert/strict";
import test from "node:test";
import { nextResultFocus } from "../src/resultFocus.ts";

test("nothing pending never moves focus", () => {
  assert.deepEqual(nextResultFocus(false, true), {
    focus: false,
    pending: false,
  });
  assert.deepEqual(nextResultFocus(false, false), {
    focus: false,
    pending: false,
  });
});

test("keeps waiting while the result is still loading", () => {
  assert.deepEqual(nextResultFocus(true, false), {
    focus: false,
    pending: true,
  });
});

test("focuses once when the result appears, then clears", () => {
  const first = nextResultFocus(true, true);
  assert.deepEqual(first, { focus: true, pending: false });
  assert.equal(nextResultFocus(first.pending, true).focus, false);
});
