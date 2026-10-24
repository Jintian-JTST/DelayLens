import type { CurvePoint } from "./api.ts";

/** Recompute locally so changing risk tolerance never sends a network request. */
export function recommend(
  points: CurvePoint[],
  tolerance: number,
  conservative = false,
): CurvePoint | null {
  return points.reduce<CurvePoint | null>((best, point) => {
    const probability = conservative ? point.ci[0] : point.p_on_time;
    if (probability + 1e-9 < 1 - tolerance) return best;
    return !best || Date.parse(point.depart_at) > Date.parse(best.depart_at)
      ? point
      : best;
  }, null);
}

export function delayedPoint(
  points: CurvePoint[],
  baseline: CurvePoint,
  minutes: number,
): CurvePoint | null {
  const target = Date.parse(baseline.depart_at) + minutes * 60_000;
  return points.find((point) => Date.parse(point.depart_at) === target) ?? null;
}
