import { test } from "node:test";
import assert from "node:assert/strict";
import { requestKey, shouldAutoRequest } from "../src/autoUpdate.ts";

const form = {
  routeId: "r",
  deadline: "2026-10-24T17:00",
  walkTo: 5,
  walkFrom: 5,
};

test("the key changes with every input a request depends on", () => {
  const base = requestKey(form, "local");
  assert.notEqual(base, requestKey({ ...form, walkTo: 7 }, "local"));
  assert.notEqual(base, requestKey({ ...form, walkFrom: 6 }, "local"));
  assert.notEqual(
    base,
    requestKey({ ...form, deadline: "2026-10-24T18:00" }, "local"),
  );
  assert.notEqual(base, requestKey({ ...form, routeId: "x" }, "local"));
  assert.notEqual(base, requestKey(form, "utc"));
  assert.equal(base, requestKey({ ...form }, "local"));
});

test("a changed valid input sends a request even when there is no result (after a failed first load)", () => {
  const lastKey = requestKey(form, "local"); // the failed first request
  const key = requestKey({ ...form, walkTo: 7 }, "local");
  assert.equal(
    shouldAutoRequest({ valid: true, catalogBusy: false, key, lastKey }),
    true,
  );
});

test("unchanged inputs do not repeat the last request", () => {
  const key = requestKey(form, "local");
  assert.equal(
    shouldAutoRequest({ valid: true, catalogBusy: false, key, lastKey: key }),
    false,
  );
});

test("invalid inputs never send", () => {
  const key = requestKey({ ...form, walkTo: 99 }, "local");
  assert.equal(
    shouldAutoRequest({
      valid: false,
      catalogBusy: false,
      key,
      lastKey: "other",
    }),
    false,
  );
});

test("nothing is sent while the catalogue is still loading", () => {
  const key = requestKey(form, "local");
  assert.equal(
    shouldAutoRequest({ valid: true, catalogBusy: true, key, lastKey: null }),
    false,
  );
});

test("after an aborted request (lastKey cleared) the same inputs are sent again", () => {
  const key = requestKey(form, "local");
  assert.equal(
    shouldAutoRequest({ valid: true, catalogBusy: false, key, lastKey: null }),
    true,
  );
});
