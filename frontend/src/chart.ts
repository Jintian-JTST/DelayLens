import type { CurvePoint } from "./api.ts";

/** The API omits unsupported minutes. Never bridge those gaps with a prediction. */
export function curveSegments(points: CurvePoint[]): CurvePoint[][] {
  const groups: CurvePoint[][] = [];
  for (const point of points) {
    const group = groups.at(-1);
    if (
      !group ||
      Date.parse(point.depart_at) - Date.parse(group.at(-1)!.depart_at) > 60_000
    ) {
      groups.push([point]);
    } else {
      group.push(point);
    }
  }
  return groups;
}
