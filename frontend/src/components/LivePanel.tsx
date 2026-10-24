import { useEffect, useState } from "react";
import { api, type LiveResponse, type Route } from "../api";
import { LIVE_UNAVAILABLE_MESSAGE, OFFLINE_LIVE_MESSAGE } from "../live";
import { timeLabel, type Clock } from "../time";
import Icon from "./Icon";

export default function LivePanel({
  route,
  demo,
  offline = false,
  clock,
}: {
  route: Route;
  demo: boolean;
  /** Offline snapshot mode: live TfL arrivals are off, so never fetch or retry. */
  offline?: boolean;
  clock: Clock;
}) {
  const [data, setData] = useState<LiveResponse | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(true);
  const [refresh, setRefresh] = useState(0);
  const [now, setNow] = useState(Date.now());
  useEffect(() => {
    setData(null);
    setError("");
    if (demo || offline) {
      setBusy(false);
      return;
    }
    let controller: AbortController;
    const load = async () => {
      controller?.abort();
      controller = new AbortController();
      const current = controller;
      setBusy(true);
      try {
        const result = await api.live(route.route_id, current.signal);
        if (!current.signal.aborted) {
          setData(result);
          setError("");
          setNow(Date.now());
        }
      } catch {
        if (!current.signal.aborted) {
          setData(null);
          setError(LIVE_UNAVAILABLE_MESSAGE);
        }
      } finally {
        if (!current.signal.aborted) setBusy(false);
      }
    };
    void load();
    const poll = window.setInterval(() => void load(), 30_000);
    const clockTick = window.setInterval(() => setNow(Date.now()), 10_000);
    return () => {
      controller?.abort();
      clearInterval(poll);
      clearInterval(clockTick);
    };
  }, [route.route_id, demo, offline, refresh]);

  return (
    <section className="card live-card" aria-label="Live arrivals">
      <div className="section-top">
        <div className="eyebrow">
          <span className={`status-dot ${data ? "green" : ""}`} />
          AT YOUR STOP
        </div>
        <button
          type="button"
          className="icon-button"
          aria-label="Refresh live arrivals"
          disabled={demo || offline || busy}
          onClick={() => setRefresh((r) => r + 1)}
        >
          <Icon name="refresh" size={17} />
        </button>
      </div>
      <h3>Next to arrive</h3>
      <p className="muted small truncate">{route.origin.name}</p>
      {demo ? (
        <div className="inline-state">
          <Icon name="info" />
          <p>
            Demonstration routes have no live vehicles. No arrivals are
            simulated.
          </p>
        </div>
      ) : offline ? (
        <div className="inline-state" role="status">
          <Icon name="info" />
          <p>{OFFLINE_LIVE_MESSAGE}</p>
        </div>
      ) : busy && !data ? (
        <div
          className="skeleton live-skeleton"
          aria-label="Loading live arrivals"
        />
      ) : error ? (
        <p className="inline-state" role="status">
          {error}
        </p>
      ) : data && data.arrivals.length === 0 ? (
        <p className="inline-state">
          No vehicles predicted right now. Arrivals refresh every 30 seconds.
        </p>
      ) : (
        <>
          <div className="arrivals">
            {data?.arrivals.slice(0, 3).map((arrival, i) => (
              <div
                className="arrival"
                key={`${arrival.vehicle_id}-${arrival.expected_arrival}-${i}`}
              >
                <span className="line-badge">{arrival.line_id}</span>
                <span className="truncate">
                  {arrival.destination_name || route.destination.name}
                </span>
                <strong>
                  {Math.max(
                    0,
                    Math.ceil(
                      (Date.parse(arrival.expected_arrival) - now) / 60_000,
                    ),
                  )}
                  <small>min</small>
                </strong>
              </div>
            ))}
          </div>
          <p className="small muted live-updated">
            Updated {data && timeLabel(data.fetched_at, clock)} · refreshes
            every 30s
          </p>
        </>
      )}
    </section>
  );
}
