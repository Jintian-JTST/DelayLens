import { useEffect, useState } from "react";
import { api, type Calibration, type Route, type Stats } from "../api";
import { zoneFor, type Clock } from "../time";
import Icon from "./Icon";

export default function Methodology({
  routes,
  demo,
  clock,
}: {
  routes: Route[];
  demo: boolean;
  clock: Clock;
}) {
  const [stats, setStats] = useState<Stats | null>(null);
  const [calibration, setCalibration] = useState<Calibration | null>(null);
  const [busy, setBusy] = useState(!demo);
  const [refresh, setRefresh] = useState(0);
  useEffect(() => {
    if (demo) return;
    const controller = new AbortController();
    setBusy(true);
    void Promise.allSettled([
      api.stats(controller.signal),
      api.calibration(controller.signal),
    ]).then(([s, c]) => {
      if (controller.signal.aborted) return;
      setStats(s.status === "fulfilled" ? s.value : null);
      setCalibration(c.status === "fulfilled" ? c.value : null);
      setBusy(false);
    });
    return () => controller.abort();
  }, [demo, refresh]);

  const hours = [...new Set(routes.flatMap((r) => r.hours_covered))].sort();
  return (
    <div className="methodology">
      <section className="card method-intro">
        <span className="eyebrow">THE METHOD, WITHOUT THE MYSTERY</span>
        <h2>Confidence should come with context.</h2>
        <p>
          DelayLens is designed to replay recorded journeys, including the wait
          at your stop. Supported departure times get an estimated on-time
          probability and a 90% uncertainty band, inferred from TfL predictions.
        </p>
        <p>
          At each departure time, 5–14 usable trips use a 90% Wilson interval;
          15 or more use a 90% run-bootstrap interval. Fewer than 5 usable trips
          show no probability or advice. Recommendations require at least 15
          usable trips for that departure time.
        </p>
        <div className="method-steps">
          <div>
            <b>01</b>
            <h3>Record TfL predictions</h3>
            <p>Capture TfL predictions over time and infer journey samples.</p>
          </div>
          <div>
            <b>02</b>
            <h3>Replay your journey</h3>
            <p>
              Compare departures with trips at a similar time of day, including
              your walks.
            </p>
          </div>
          <div>
            <b>03</b>
            <h3>Make the trade-off</h3>
            <p>
              Choose how much risk you accept. Less data means more uncertainty.
            </p>
          </div>
        </div>
        <div className="notice">
          <Icon name="info" />
          <span>
            Single-leg London routes and one Saturday (24 Oct 2026) of
            observations only. Arrivals are inferred from TfL predictions, not
            measured, so every figure is an estimate, not a guarantee. Fixture
            results are synthetic and do not validate this method.
          </span>
        </div>
      </section>
      <div className="method-grid">
        <section className="card">
          <div className="section-top">
            <span className="eyebrow">DATA COVERAGE</span>
            <button
              className="icon-button"
              type="button"
              disabled={demo || busy}
              aria-label="Refresh methodology data"
              onClick={() => setRefresh((r) => r + 1)}
            >
              <Icon name="refresh" size={17} />
            </button>
          </div>
          <h3>The observations behind it</h3>
          <div className="stats-grid">
            <div>
              <strong>{stats ? stats.rows.toLocaleString() : "—"}</strong>
              <span>prediction rows</span>
            </div>
            <div>
              <strong>{stats ? stats.chunks.toLocaleString() : "—"}</strong>
              <span>database chunks</span>
            </div>
            <div>
              <strong>
                {stats?.compression_ratio != null
                  ? `${stats.compression_ratio.toFixed(1)}×`
                  : "—"}
              </strong>
              <span>compression</span>
            </div>
          </div>
          {busy ? (
            <p role="status" className="muted">
              Loading database coverage…
            </p>
          ) : (
            !stats && (
              <p className="inline-state">
                {demo
                  ? "The demo has no recorded observations."
                  : "Database statistics are not connected yet."}
              </p>
            )
          )}
          <h4>Recorded hours · {zoneFor(clock)}</h4>
          {hours.length ? (
            <div
              className="coverage-hours"
              tabIndex={0}
              role="region"
              aria-label="Scrollable route coverage table"
            >
              <table className="coverage-table">
                <caption>
                  Reported coverage by route and hour. Purple cells indicate a
                  covered hour; blank cells mean no coverage was reported.
                </caption>
                <thead>
                  <tr>
                    <th scope="col">Route</th>
                    {hours.map((hour) => (
                      <th scope="col" key={hour}>
                        {new Intl.DateTimeFormat("en-GB", {
                          month: "short",
                          day: "numeric",
                          hour: "2-digit",
                          timeZone: zoneFor(clock),
                          timeZoneName: "short",
                        }).format(new Date(hour))}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {routes.map((route) => (
                    <tr key={route.route_id}>
                      <th scope="row">
                        {route.origin.name} → {route.destination.name}
                      </th>
                      {hours.map((hour) => {
                        const covered = route.hours_covered.some(
                          (value) => Date.parse(value) === Date.parse(hour),
                        );
                        return (
                          <td key={hour}>
                            <span
                              className={`coverage-cell ${covered ? "covered" : ""}`}
                              title={`${route.origin.name} → ${route.destination.name}: ${hour}`}
                            >
                              <span className="sr-only">
                                {covered
                                  ? "Coverage reported"
                                  : "No coverage reported"}
                              </span>
                            </span>
                          </td>
                        );
                      })}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <p className="small muted">
              No recorded hours reported. Choose demo data only to explore the
              interface.
            </p>
          )}
        </section>
        <section className="card">
          <span className="eyebrow">CHECKING OUR CONFIDENCE</span>
          <h3>Does 80% mean 80%?</h3>
          <p className="small muted">
            Predicted probability compared with inferred stop events on held-out
            journeys. This does not validate actual arrival times.
          </p>
          {calibration && (
            <div className="notice calibration-status">
              <Icon name="shield" />
              <div>
                <strong>
                  {calibration.calibration_status === "preliminary"
                    ? "Preliminary backtest · not validated"
                    : "Calibration not validated"}
                </strong>
                <p>
                  {(calibration.n_outcomes ?? 0).toLocaleString()} scored
                  outcomes
                  {" · "}
                  {(calibration.n_runs ?? 0).toLocaleString()} distinct runs
                </p>
                {calibration.basis && <p>{calibration.basis}</p>}
              </div>
            </div>
          )}
          {calibration?.bins.length ? (
            <>
              <svg
                viewBox="0 0 300 200"
                className="calibration-chart"
                role="img"
                aria-label="Calibration: predicted versus observed on-time probability"
              >
                <path d="M30 15V170H285" fill="none" stroke="#c8c6cf" />
                <path
                  d="m30 170 255-155"
                  fill="none"
                  stroke="#a7a1b4"
                  strokeDasharray="4 4"
                />
                {calibration.bins.map((bin, i) => (
                  <circle
                    key={i}
                    cx={30 + bin.predicted * 255}
                    cy={170 - bin.observed * 155}
                    r="5"
                    fill="#7961bf"
                  >
                    <title>
                      Predicted {Math.round(bin.predicted * 100)}%; observed{" "}
                      {Math.round(bin.observed * 100)}%; {bin.n} samples
                    </title>
                  </circle>
                ))}
                <text x="30" y="190" className="axis-text">
                  0%
                </text>
                <text x="260" y="190" className="axis-text">
                  100%
                </text>
              </svg>
              <p className="small">
                Brier score:{" "}
                <strong>
                  {calibration.brier_score?.toFixed(3) ?? "Unavailable"}
                </strong>{" "}
                · lower is better
              </p>
            </>
          ) : (
            <div className="calibration-empty">
              <Icon name="shield" size={32} />
              <strong>
                {busy
                  ? "Loading calibration…"
                  : calibration
                    ? "No scored backtest outcomes yet"
                    : "Calibration is not available yet"}
              </strong>
              <p>
                {calibration
                  ? "More recorded journeys are needed before the backtest can be shown."
                  : "We will show backtest results when the service is available."}
              </p>
            </div>
          )}
        </section>
      </div>
    </div>
  );
}
