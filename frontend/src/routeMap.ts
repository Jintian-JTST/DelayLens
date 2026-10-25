import type { CurvePoint, Route, Stop } from "./api.ts";

/**
 * Pure helpers for the schematic journey map (RouteMap.tsx). The map is our own
 * schematic drawing, not to scale and not TfL artwork. Our data is
 * origin-to-destination trips only, so nothing here places a delay at an
 * intermediate stop: uncertainty is attributed to the wait and the whole ride.
 */

/** The bus 29 demo route; the only route the schematic is drawn for. */
export const MAP_ROUTE_ID =
  "bus-29-outbound-mornington-crescent-tottenham-court-road";

/** The configured stop sequence for the demo route, or null when unavailable. */
export function mapStops(route: Route | null | undefined): Stop[] | null {
  if (!route || route.route_id !== MAP_ROUTE_ID) return null;
  const stops = route.stops ?? [];
  return stops.length >= 2 ? stops : null;
}

/** Split a stop name into short lines for SVG labels (no mid-word breaks). */
export function wrapLabel(name: string, maxChars = 14): string[] {
  const lines: string[] = [];
  for (const word of name.split(/\s+/).filter(Boolean)) {
    const last = lines.at(-1);
    if (last !== undefined && `${last} ${word}`.length <= maxChars)
      lines[lines.length - 1] = `${last} ${word}`;
    else lines.push(word);
  }
  return lines;
}

export interface MapPoint {
  x: number;
  y: number;
}
export interface StopLayout {
  points: MapPoint[];
  /** Index of the last stop before the 45-degree bend. */
  bendAfter: number;
  path: string;
}

export const MAP_GEOMETRY = {
  width: 880,
  startX: 130,
  spacing: 86,
  topY: 92,
  drop: 70,
} as const;

/**
 * Tube-map layout: a horizontal run, one 45-degree diagonal, a second
 * horizontal run. Stops sit only on the horizontal runs.
 */
export function layoutStops(count: number, g = MAP_GEOMETRY): StopLayout {
  const bendAfter = Math.max(0, Math.floor((count - 1) / 2));
  const points: MapPoint[] = [];
  for (let i = 0; i < count; i++) {
    if (i <= bendAfter) points.push({ x: g.startX + i * g.spacing, y: g.topY });
    else
      points.push({
        // The diagonal covers `drop` horizontally (45 degrees), then half a gap.
        x: g.startX + bendAfter * g.spacing + g.drop + (i - bendAfter - 0.5) * g.spacing,
        y: g.topY + g.drop,
      });
  }
  if (!points.length) return { points, bendAfter, path: "" };
  const corner = points[bendAfter];
  const segments = [`M${points[0].x},${points[0].y}`, `L${corner.x},${corner.y}`];
  if (count > bendAfter + 1) {
    segments.push(`L${corner.x + g.drop},${corner.y + g.drop}`);
    const end = points.at(-1)!;
    segments.push(`L${end.x},${end.y}`);
  }
  return { points, bendAfter, path: segments.join(" ") };
}

export type LegKind = "walk" | "ride" | "spread";
export interface Leg {
  kind: LegKind;
  start: number;
  end: number;
}
export interface TimelineRow {
  label: string;
  legs: Leg[];
  arrive: number;
}
export interface JourneyTimeline {
  leave: number;
  atStop: number;
  stopP50: number;
  stopP90: number;
  arriveP50: number;
  arriveP90: number;
  deadline: number;
  /** Typical wait plus ride, in minutes (p50). */
  waitRideMin: number;
  /** Extra minutes between the typical (p50) and slow (p90) arrival. */
  spreadMin: number;
  /** Minutes to spare at p90; negative when p90 arrives after the deadline. */
  slackP90Min: number;
  rows: [TimelineRow, TimelineRow];
}

const minutes = (ms: number) => Math.round(ms / 60_000);

/**
 * Split the selected departure into legs. `depart_at` is when you leave; the
 * curve's arrival percentiles already include both walks. Only the wait plus
 * ride varies between replayed trips.
 */
export function journeyTimeline(
  point: CurvePoint,
  walkToMin: number,
  walkFromMin: number,
  deadlineIso: string,
): JourneyTimeline {
  const leave = Date.parse(point.depart_at);
  const atStop = leave + walkToMin * 60_000;
  const arriveP50 = Math.max(atStop + walkFromMin * 60_000, Date.parse(point.arrive_p50));
  const arriveP90 = Math.max(arriveP50, Date.parse(point.arrive_p90));
  const stopP50 = arriveP50 - walkFromMin * 60_000;
  const stopP90 = arriveP90 - walkFromMin * 60_000;
  const deadline = Date.parse(deadlineIso);
  const typical: TimelineRow = {
    label: "Typical (p50)",
    legs: [
      { kind: "walk", start: leave, end: atStop },
      { kind: "ride", start: atStop, end: stopP50 },
      { kind: "walk", start: stopP50, end: arriveP50 },
    ],
    arrive: arriveP50,
  };
  const slow: TimelineRow = {
    label: "Slower (p90)",
    legs: [
      { kind: "walk", start: leave, end: atStop },
      { kind: "ride", start: atStop, end: stopP50 },
      { kind: "spread", start: stopP50, end: stopP90 },
      { kind: "walk", start: stopP90, end: arriveP90 },
    ],
    arrive: arriveP90,
  };
  return {
    leave,
    atStop,
    stopP50,
    stopP90,
    arriveP50,
    arriveP90,
    deadline,
    waitRideMin: minutes(stopP50 - atStop),
    spreadMin: minutes(arriveP90 - arriveP50),
    slackP90Min: minutes(deadline - arriveP90),
    rows: [typical, slow],
  };
}

/** One-sentence summary for the map's accessible name. */
export function journeySummary(
  timeline: JourneyTimeline,
  stops: Stop[],
  format: (ms: number) => string,
  chancePercent: number | null,
): string {
  const from = stops[0].name;
  const to = stops.at(-1)!.name;
  const chance =
    chancePercent === null ? "" : ` Estimated ${chancePercent}% chance of arriving on time.`;
  return (
    `Schematic map of bus 29 from ${from} to ${to}, ${stops.length} stops. ` +
    `Leave ${format(timeline.leave)}, reach the stop about ${format(timeline.atStop)}, ` +
    `typical arrival ${format(timeline.arriveP50)}, 9 in 10 replayed trips by ` +
    `${format(timeline.arriveP90)}, deadline ${format(timeline.deadline)}.${chance} ` +
    "Delays at individual stops are not measured."
  );
}

/** "+7 min" / "on time" / "3 min late" wording for the p90 margin. */
export function slackLabel(slackMin: number): string {
  if (slackMin > 0) return `${slackMin} min to spare at p90`;
  if (slackMin === 0) return "p90 lands on the deadline";
  return `p90 is ${-slackMin} min after the deadline`;
}
