import { test } from "node:test";
import assert from "node:assert/strict";
import type { CurvePoint, Route } from "../src/api.ts";
import {
  MAP_ROUTE_ID,
  journeySummary,
  journeyTimeline,
  layoutStops,
  mapStops,
  slackLabel,
  wrapLabel,
} from "../src/routeMap.ts";

const names = [
  "Mornington Crescent Station",
  "Silverdale",
  "William Road",
  "Warren Street Station / Euston Road",
  "Capper Street",
  "Goodge Street Station",
  "Stephen Street",
  "Tottenham Court Road Station",
];
const route = (overrides: Partial<Route> = {}): Route => ({
  route_id: MAP_ROUTE_ID,
  line_id: "29",
  mode: "bus",
  origin: { naptan_id: "O", name: names[0] },
  destination: { naptan_id: "D", name: names[7] },
  trips_observed: 40,
  hours_covered: [],
  stops: names.map((name, i) => ({ naptan_id: `S${i}`, name })),
  ...overrides,
});

test("the map is only drawn for the bus 29 demo route with stops", () => {
  assert.equal(mapStops(route())?.length, 8);
  assert.equal(mapStops(route({ route_id: "bus-24-inbound-warren-tottenham" })), null);
  assert.equal(mapStops(route({ stops: undefined })), null);
  assert.equal(mapStops(route({ stops: null })), null);
  assert.equal(mapStops(null), null);
});

test("labels wrap on word boundaries", () => {
  assert.deepEqual(wrapLabel("Warren Street Station / Euston Road"), [
    "Warren Street",
    "Station /",
    "Euston Road",
  ]);
  assert.deepEqual(wrapLabel("Silverdale"), ["Silverdale"]);
  assert.deepEqual(wrapLabel(""), []);
});

test("layout uses horizontal runs and one 45-degree diagonal", () => {
  const { points, bendAfter, path } = layoutStops(8);
  assert.equal(bendAfter, 3);
  assert.ok(points.slice(0, 4).every((p) => p.y === points[0].y));
  assert.ok(points.slice(4).every((p) => p.y === points[4].y));
  // Equal horizontal and vertical travel on the diagonal is a 45-degree angle.
  const drop = points[4].y - points[3].y;
  assert.equal(path, `M130,92 L388,92 L${388 + drop},${92 + drop} L759,162`);
  for (let i = 1; i < points.length; i++) assert.ok(points[i].x > points[i - 1].x);
  assert.equal(layoutStops(0).path, "");
});

const point: CurvePoint = {
  depart_at: "2026-10-24T15:22:00Z",
  p_on_time: 0.92,
  ci: [0.8, 0.97],
  arrive_p50: "2026-10-24T15:45:00Z",
  arrive_p90: "2026-10-24T15:52:00Z",
  n_trips: 18,
};

test("timeline splits a departure into walks, wait+ride and the p50-p90 spread", () => {
  const t = journeyTimeline(point, 5, 5, "2026-10-24T16:00:00Z");
  assert.equal(t.atStop, Date.parse("2026-10-24T15:27:00Z"));
  assert.equal(t.stopP50, Date.parse("2026-10-24T15:40:00Z"));
  assert.equal(t.stopP90, Date.parse("2026-10-24T15:47:00Z"));
  assert.equal(t.waitRideMin, 13);
  assert.equal(t.spreadMin, 7);
  assert.equal(t.slackP90Min, 8);
  const [typical, slow] = t.rows;
  assert.deepEqual(
    typical.legs.map((l) => l.kind),
    ["walk", "ride", "walk"],
  );
  assert.deepEqual(
    slow.legs.map((l) => l.kind),
    ["walk", "ride", "spread", "walk"],
  );
  assert.equal(typical.arrive, t.arriveP50);
  assert.equal(slow.arrive, t.arriveP90);
  // Walks keep their length; only the wait and ride vary.
  assert.equal(slow.legs[3].end - slow.legs[3].start, 5 * 60_000);
});

test("timeline never shows a negative wait or reversed percentiles", () => {
  const odd = { ...point, arrive_p50: "2026-10-24T15:25:00Z", arrive_p90: "2026-10-24T15:20:00Z" };
  const t = journeyTimeline(odd, 5, 5, "2026-10-24T15:30:00Z");
  assert.ok(t.stopP50 >= t.atStop);
  assert.ok(t.arriveP90 >= t.arriveP50);
  assert.equal(t.waitRideMin, 0);
});

test("summary names the route, times and the per-stop caveat", () => {
  const t = journeyTimeline(point, 5, 5, "2026-10-24T16:00:00Z");
  const fmt = (ms: number) => new Date(ms).toISOString().slice(11, 16);
  const text = journeySummary(t, route().stops!, fmt, 92);
  assert.match(text, /Mornington Crescent Station to Tottenham Court Road Station, 8 stops/);
  assert.match(text, /Leave 15:22, reach the stop about 15:27/);
  assert.match(text, /typical arrival 15:45, 9 in 10 replayed trips by 15:52, deadline 16:00/);
  assert.match(text, /Estimated 92% chance/);
  assert.match(text, /not measured/);
  assert.doesNotMatch(journeySummary(t, route().stops!, fmt, null), /chance/);
});

test("slack wording covers spare, exact and late p90", () => {
  assert.equal(slackLabel(8), "8 min to spare at p90");
  assert.equal(slackLabel(0), "p90 lands on the deadline");
  assert.equal(slackLabel(-3), "p90 is 3 min after the deadline");
});
