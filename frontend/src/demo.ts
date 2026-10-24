import type { CurveRequest, CurveResponse, Route } from "./api";

/** Explicitly selected design fixtures; never a fallback for failed API requests. */
export const demoRoutes: Route[] = [
  {
    route_id: "demo-bus-outbound",
    line_id: "DEMO",
    mode: "bus",
    origin: { naptan_id: "DEMO-O", name: "Camden Town" },
    destination: { naptan_id: "DEMO-D", name: "Oxford Circus" },
    trips_observed: 0,
    hours_covered: [],
  },
];

export function demoCurve(request: CurveRequest): CurveResponse {
  const deadline = Date.parse(request.deadline);
  const journey = 30 + request.walk_to_min + request.walk_from_min;
  return {
    points: Array.from({ length: request.window_min + 1 }, (_, index) => {
      const minutes = request.window_min - index;
      const depart = deadline - minutes * 60_000;
      const probability = 1 / (1 + Math.exp(-(minutes - journey - 10) / 3));
      return {
        depart_at: new Date(depart).toISOString(),
        p_on_time: probability,
        ci: [Math.max(0, probability - 0.06), Math.min(1, probability + 0.06)],
        arrive_p50: new Date(depart + (journey + 10) * 60_000).toISOString(),
        arrive_p90: new Date(depart + (journey + 18) * 60_000).toISOString(),
        n_trips: 40,
      };
    }),
    recommended: null,
    what_if: [],
    data_quality: {
      status: "ok",
      basis:
        "DEMO FIXTURE: synthetic probabilities and sample counts. No recorded trips or live arrivals.",
    },
    server_ms: 0,
  };
}
