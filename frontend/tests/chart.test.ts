import { test } from "node:test";
import assert from "node:assert/strict";
import { curveSegments } from "../src/chart.ts";
import type { CurvePoint } from "../src/api.ts";

const point = (minute: number): CurvePoint => ({
  depart_at: new Date(Date.UTC(2026, 9, 24, 14, minute)).toISOString(),
  p_on_time: 0.8,
  ci: [0.5, 0.95],
  n_trips: 8,
  arrive_p50: "2026-10-24T15:00:00Z",
  arrive_p90: "2026-10-24T15:10:00Z",
});

test("gaps in observed minutes split the probability and uncertainty paths", () => {
  const points = [point(0), point(1), point(4), point(5), point(8)];
  assert.deepEqual(
    curveSegments(points).map((group) => group.length),
    [2, 2, 1],
  );
});
test("empty and single-point curves are supported without inventing points", () => {
  assert.deepEqual(curveSegments([]), []);
  assert.deepEqual(curveSegments([point(0)]), [[point(0)]]);
});
