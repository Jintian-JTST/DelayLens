import { test } from "node:test";
import assert from "node:assert/strict";
import {
  DEFAULT_ROUTE_ID,
  exampleDeadline,
  isCovered,
  pickInitialRoute,
} from "../src/defaults.ts";
import { inputDate } from "../src/time.ts";
import type { Route } from "../src/api.ts";

const route = (id: string, trips: number, hours: string[] = []): Route =>
  ({ route_id: id, trips_observed: trips, hours_covered: hours }) as Route;
const hours = Array.from(
  { length: 6 },
  (_, i) => `2026-10-24T${String(14 + i).padStart(2, "0")}:00:00Z`,
);

test("bus 29 Mornington Crescent is the initial route even if others have more trips", () => {
  const list = [route("victoria-line", 9999), route(DEFAULT_ROUTE_ID, 10)];
  assert.equal(pickInitialRoute(list)?.route_id, DEFAULT_ROUTE_ID);
});
test("falls back to the most-observed route when bus 29 is absent", () => {
  const list = [route("a", 1), route("b", 5)];
  assert.equal(pickInitialRoute(list)?.route_id, "b");
  assert.equal(pickInitialRoute([]), undefined);
});
test("example deadline is Saturday 17:00 London, not the latest covered hour", () => {
  const iso = exampleDeadline(route(DEFAULT_ROUTE_ID, 1, hours))!;
  assert.equal(iso, "2026-10-24T16:00:00.000Z");
  assert.equal(inputDate(iso, "utc"), "2026-10-24T16:00");
});
test("example deadline falls back to the latest covered hour outside the preferred day", () => {
  const other = ["2026-10-20T08:00:00Z", "2026-10-20T09:00:00Z"];
  assert.equal(
    exampleDeadline(route("x", 1, other)),
    "2026-10-20T09:00:00.000Z",
  );
  assert.equal(exampleDeadline(route("x", 1)), null);
});
test("isCovered matches the recorded hour containing a time", () => {
  const r = route("x", 1, hours);
  assert.equal(isCovered(r, "2026-10-24T16:40:00Z"), true);
  assert.equal(isCovered(r, "2026-10-25T16:40:00Z"), false);
});
