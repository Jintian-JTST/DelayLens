/** Mirrors backend/app/schemas.py. Timestamps cross the boundary as ISO 8601 strings. */
export interface Stop {
  naptan_id: string;
  name: string;
}
export interface Route {
  route_id: string;
  line_id: string;
  mode: "bus" | "tube";
  origin: Stop;
  destination: Stop;
  trips_observed: number;
  hours_covered: string[];
}
export interface CurveRequest {
  route_id: string;
  deadline: string;
  walk_to_min: number;
  walk_from_min: number;
  tolerance: number;
  window_min: number;
}
export interface CurvePoint {
  depart_at: string;
  p_on_time: number;
  ci: [number, number];
  arrive_p50: string;
  arrive_p90: string;
  n_trips: number;
}
export interface CurveResponse {
  points: CurvePoint[];
  recommended: { depart_at: string; p_on_time: number } | null;
  what_if: { delay_min: number; p_on_time: number; delta: number }[];
  data_quality: {
    status: "ok" | "low_data" | "insufficient_data";
    basis: string;
  };
  server_ms: number;
}
export interface Interpretation {
  route_id: string | null;
  deadline: string | null;
  walk_to_min: number | null;
  walk_from_min: number | null;
  tolerance: number | null;
  compare: string[] | null;
}
export interface AskResponse {
  interpretation: Interpretation;
  curve: CurveResponse | null;
  answer: string;
  status: "ok" | "unsupported_route" | "unclear" | "gemini_unavailable";
}
export interface LiveResponse {
  route_id: string;
  fetched_at: string;
  arrivals: {
    vehicle_id: string;
    line_id: string;
    destination_name: string | null;
    time_to_station_s: number;
    expected_arrival: string;
  }[];
}
export interface Stats {
  rows: number;
  chunks: number;
  compression_ratio: number | null;
  first_polled_at: string | null;
  last_polled_at: string | null;
}
export interface Calibration {
  bins: { predicted: number; observed: number; n: number }[];
  brier_score: number | null;
  calibration_status: "not_validated" | "preliminary";
  n_outcomes: number;
  n_runs: number;
  basis: string;
}

const base = (import.meta.env.VITE_API_BASE_URL || "").replace(/\/$/, "");

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

async function request<T>(
  path: string,
  body?: unknown,
  signal?: AbortSignal,
  headers: Record<string, string> = {},
): Promise<T> {
  const response = await fetch(`${base}/api/${path}`, {
    signal: signal
      ? AbortSignal.any([signal, AbortSignal.timeout(12_000)])
      : AbortSignal.timeout(12_000),
    ...(body === undefined
      ? {}
      : {
          method: "POST",
          headers: { "Content-Type": "application/json", ...headers },
          body: JSON.stringify(body),
        }),
  });
  if (!response.ok) {
    throw new ApiError(
      response.status,
      response.status === 503
        ? "This service is not available yet. Please try again shortly."
        : `The request could not be completed (${response.status}).`,
    );
  }
  return response.json() as Promise<T>;
}

export const api = {
  routes: (signal?: AbortSignal) =>
    request<Route[]>("routes", undefined, signal),
  curve: (body: CurveRequest, signal?: AbortSignal) =>
    request<CurveResponse>("departure-curve", body, signal),
  /** `accessCode` is the team passcode when the server sets ASK_ACCESS_CODE. */
  ask: (question: string, signal?: AbortSignal, accessCode = "") =>
    request<AskResponse>(
      "ask",
      { question },
      signal,
      accessCode ? { "X-Ask-Access-Code": accessCode } : {},
    ),
  live: (route: string, signal?: AbortSignal) =>
    request<LiveResponse>(
      `live?route_id=${encodeURIComponent(route)}`,
      undefined,
      signal,
    ),
  stats: (signal?: AbortSignal) => request<Stats>("stats", undefined, signal),
  calibration: (signal?: AbortSignal) =>
    request<Calibration>("calibration", undefined, signal),
};
