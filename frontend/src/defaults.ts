import type { Route } from "./api";

/** Team-confirmed main route: London bus 29, Mornington Crescent -> Tottenham Court Road. */
export const DEFAULT_ROUTE_ID =
  "bus-29-outbound-mornington-crescent-tottenham-court-road";
/** Saturday 2026-10-24 17:00 London (BST, UTC+1) = 16:00Z, inside the recorded hours. */
export const PREFERRED_EXAMPLE_DEADLINE = "2026-10-24T16:00:00.000Z";

const HOUR_MS = 3_600_000;

/** Bus 29 when the catalogue has it; otherwise the most-observed route. */
export function pickInitialRoute(routes: Route[]): Route | undefined {
  return (
    routes.find((route) => route.route_id === DEFAULT_ROUTE_ID) ??
    routes.reduce<Route | undefined>(
      (best, route) =>
        !best || route.trips_observed > best.trips_observed ? route : best,
      undefined,
    )
  );
}

/**
 * Deadline used by the recorded-hour example button and the initial form when
 * the default deadline has no recorded data. Prefers Saturday 17:00 London when
 * the route's recorded hours cover it (later edge hours only hold p=1.00
 * points); otherwise falls back to the latest covered hour.
 */
export function exampleDeadline(route: Route): string | null {
  const hours = route.hours_covered
    .map((hour) => Date.parse(hour))
    .filter(Number.isFinite);
  if (!hours.length) return null;
  const preferred = Date.parse(PREFERRED_EXAMPLE_DEADLINE);
  if (
    preferred >= Math.min(...hours) &&
    preferred <= Math.max(...hours) + HOUR_MS
  )
    return PREFERRED_EXAMPLE_DEADLINE;
  return new Date(Math.max(...hours)).toISOString();
}

/** True when the hour containing `iso` is among the route's recorded hours. */
export function isCovered(route: Route, iso: string): boolean {
  const hour = Math.floor(Date.parse(iso) / HOUR_MS) * HOUR_MS;
  return route.hours_covered.some((h) => Date.parse(h) === hour);
}
