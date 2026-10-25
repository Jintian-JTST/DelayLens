import type { Route, Stop } from "./api";

/** A route the planner can answer for: recorded trips exist (or it is the labelled fixture). */
export const isUsableRoute = (route: Route): boolean =>
  route.line_id === "fixture" || route.trips_observed > 0;

/** Routes without observed trips cannot be estimated, so they are not offered. */
export const usableRoutes = (routes: Route[]): Route[] =>
  routes.filter(isUsableRoute);

const unique = (stops: Stop[]): Stop[] => {
  const seen = new Set<string>();
  return stops.filter((stop) => {
    if (seen.has(stop.naptan_id)) return false;
    seen.add(stop.naptan_id);
    return true;
  });
};

const byEvidence = (a: Route, b: Route) => b.trips_observed - a.trips_observed;

/** Distinct starting points, best-observed first. */
export const originsOf = (routes: Route[]): Stop[] =>
  unique([...routes].sort(byEvidence).map((route) => route.origin));

/** Destinations reachable from one starting point. */
export const destinationsFor = (routes: Route[], originId: string): Stop[] =>
  unique(
    [...routes]
      .filter((route) => route.origin.naptan_id === originId)
      .sort(byEvidence)
      .map((route) => route.destination),
  );

export const routeFor = (
  routes: Route[],
  originId: string,
  destinationId: string,
): Route | undefined =>
  routes.find(
    (route) =>
      route.origin.naptan_id === originId &&
      route.destination.naptan_id === destinationId,
  );

/**
 * Apply a change to the starting point or the destination. A new starting point
 * keeps the current destination when that pair exists, otherwise takes the
 * best-observed destination from it.
 */
export function reselect(
  routes: Route[],
  current: Route | undefined,
  change: { origin?: string; destination?: string },
): Route | undefined {
  if (change.destination !== undefined) {
    const originId = current?.origin.naptan_id ?? routes[0]?.origin.naptan_id;
    return originId
      ? routeFor(routes, originId, change.destination)
      : undefined;
  }
  if (change.origin !== undefined) {
    const keep = current
      ? routeFor(routes, change.origin, current.destination.naptan_id)
      : undefined;
    if (keep) return keep;
    const [first] = destinationsFor(routes, change.origin);
    return first ? routeFor(routes, change.origin, first.naptan_id) : undefined;
  }
  return current;
}
