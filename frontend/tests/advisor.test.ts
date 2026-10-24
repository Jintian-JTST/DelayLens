import { test } from "node:test";
import assert from "node:assert/strict";
import { recommend, delayedPoint } from "../src/advisor.ts";
import type { CurvePoint } from "../src/api.ts";

const point = (
  minute: number,
  probability: number,
  lower = probability,
): CurvePoint => ({
  depart_at: new Date(Date.UTC(2026, 9, 25, 0, minute)).toISOString(),
  p_on_time: probability,
  ci: [lower, Math.min(1, probability + 0.05)],
  arrive_p50: "2026-10-25T01:00:00Z",
  arrive_p90: "2026-10-25T01:10:00Z",
  n_trips: 38,
});

test("chooses the latest departure meeting tolerance, even if points are unordered", () => {
  const points = [point(20, 0.9), point(10, 0.95), point(30, 0.7)];
  assert.equal(recommend(points, 0.1)?.depart_at, point(20, 0.9).depart_at);
});
test("conservative advice uses the lower uncertainty bound", () => {
  const points = [point(10, 0.98, 0.94), point(20, 0.94, 0.87)];
  assert.equal(recommend(points, 0.1, true)?.depart_at, points[0].depart_at);
  assert.equal(recommend(points, 0.1, false)?.depart_at, points[1].depart_at);
});
test("returns no recommendation when the target cannot be met", () => {
  assert.equal(recommend([point(10, 0.8)], 0.05), null);
  assert.equal(recommend([], 0.1), null);
});
test("what-if returns the exact curve point and never fabricates an out-of-window risk", () => {
  const points = [point(10, 0.95), point(15, 0.8)];
  assert.equal(delayedPoint(points, points[0], 5), points[1]);
  assert.equal(delayedPoint(points, points[0], 10), null);
});
test("what-if arithmetic remains absolute across the UK clock change", () => {
  const before = { ...point(0, 0.9), depart_at: "2026-10-25T01:55:00+01:00" };
  const after = { ...point(0, 0.8), depart_at: "2026-10-25T01:00:00Z" };
  assert.equal(delayedPoint([before, after], before, 5), after);
});
