import { test } from "node:test";
import assert from "node:assert/strict";
import type { Route, Stop } from "../src/api.ts";
import {
  destinationsFor,
  originsOf,
  reselect,
  routeFor,
  usableRoutes,
} from "../src/routePicker.ts";

const stop = (id: string, name: string): Stop => ({ naptan_id: id, name });
const MORN = stop("m", "Mornington Crescent");
const FINS = stop("f", "Finsbury Park");
const TCR = stop("t", "Tottenham Court Road");
const BRIX = stop("b", "Brixton");
const OXC = stop("o", "Oxford Circus");
const route = (
  id: string,
  origin: Stop,
  destination: Stop,
  trips: number,
  line = "29",
): Route => ({
  route_id: id,
  line_id: line,
  mode: "bus",
  origin,
  destination,
  trips_observed: trips,
  hours_covered: [],
});
const routes = [
  route("short", MORN, TCR, 80),
  route("long", FINS, TCR, 70),
  route("tube", BRIX, OXC, 0, "victoria"),
  route("bus24", MORN, OXC, 0, "24"),
];

test("routes without observed trips are not offered", () => {
  assert.deepEqual(
    usableRoutes(routes).map((r) => r.route_id),
    ["short", "long"],
  );
});

test("the labelled fixture stays selectable with zero trips", () => {
  const fixture = route("demo", MORN, TCR, 0, "fixture");
  assert.equal(usableRoutes([fixture]).length, 1);
});

test("origins are distinct and best-observed first", () => {
  assert.deepEqual(
    originsOf(usableRoutes(routes)).map((s) => s.name),
    ["Mornington Crescent", "Finsbury Park"],
  );
});

test("destinations depend on the chosen origin", () => {
  const usable = usableRoutes(routes);
  assert.deepEqual(
    destinationsFor(usable, "m").map((s) => s.name),
    ["Tottenham Court Road"],
  );
  assert.deepEqual(destinationsFor(usable, "unknown"), []);
});

test("changing the origin keeps the destination when that pair exists", () => {
  const usable = usableRoutes(routes);
  const next = reselect(usable, usable[0], { origin: "f" });
  assert.equal(next?.route_id, "long");
});

test("changing the origin falls back to its best destination", () => {
  const pairs = [route("a", MORN, TCR, 10), route("b", FINS, OXC, 5)];
  const next = reselect(pairs, pairs[0], { origin: "f" });
  assert.equal(next?.route_id, "b");
});

test("changing the destination stays on the same origin", () => {
  const pairs = [route("a", MORN, TCR, 10), route("b", MORN, OXC, 5)];
  assert.equal(reselect(pairs, pairs[0], { destination: "o" })?.route_id, "b");
  assert.equal(reselect(pairs, pairs[0], { destination: "x" }), undefined);
});

test("routeFor needs both ends", () => {
  assert.equal(routeFor(routes, "m", "t")?.route_id, "short");
  assert.equal(routeFor(routes, "f", "o"), undefined);
});
