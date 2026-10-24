import { test } from "node:test";
import assert from "node:assert/strict";
import { demoRequested } from "../src/demoFlag.ts";

test("demo toggle is hidden by default", () => {
  assert.equal(demoRequested(""), false);
  assert.equal(demoRequested("?route=29", "#plan"), false);
});
test("?demo=1 enables the demo toggle", () => {
  assert.equal(demoRequested("?demo=1"), true);
  assert.equal(demoRequested("?x=2&demo=1"), true);
  assert.equal(demoRequested("?demo=true"), true);
});
test("demo flag inside the hash is tolerated", () => {
  assert.equal(demoRequested("", "#demo=1"), true);
  assert.equal(demoRequested("", "#/plan?demo=1"), true);
});
test("other demo values do not enable the toggle", () => {
  assert.equal(demoRequested("?demo=0"), false);
  assert.equal(demoRequested("?demo="), false);
  assert.equal(demoRequested("?nodemo=1"), false);
  assert.equal(demoRequested("", "#demo=no"), false);
});
