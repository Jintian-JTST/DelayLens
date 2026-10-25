import type { CurvePoint, Route } from "../api";
import {
  MAP_GEOMETRY as G,
  journeySummary,
  journeyTimeline,
  layoutStops,
  mapStops,
  slackLabel,
  wrapLabel,
} from "../routeMap";
import { timeLabel, type Clock } from "../time";
import Icon from "./Icon";

interface Props {
  route: Route;
  /** The departure shown in the advice card (recommendation or what-if). */
  point: CurvePoint | null;
  walkTo: number;
  walkFrom: number;
  deadline: string;
  clock: Clock;
  /** On-time chance shown in the advice card, as a whole percent. */
  chancePercent: number | null;
  chanceLabel: string;
  preliminary: boolean;
}

const HEIGHT = 236;
const END_X = 840;

export default function RouteMap({
  route,
  point,
  walkTo,
  walkFrom,
  deadline,
  clock,
  chancePercent,
  chanceLabel,
  preliminary,
}: Props) {
  const stops = mapStops(route);
  if (!stops)
    return (
      <section className="card map-card" aria-labelledby="map-title">
        <MapHeading />
        <div className="inline-state">
          <Icon name="map" />
          <p>
            The schematic map is not available for the labelled demonstration
            route.
          </p>
        </div>
      </section>
    );

  const fmt = (ms: number) => timeLabel(new Date(ms).toISOString(), clock);
  const layout = layoutStops(stops.length);
  const { points } = layout;
  const origin = points[0];
  const end = points.at(-1)!;
  const timeline = point
    ? journeyTimeline(point, walkTo, walkFrom, deadline)
    : null;
  const summary = timeline
    ? journeySummary(timeline, stops, fmt, chancePercent)
    : `Schematic map of bus 29 from ${stops[0].name} to ${stops.at(-1)!.name}, ${stops.length} stops. No departure is highlighted because there is no recommendation for this deadline.`;

  return (
    <section className="card map-card" aria-labelledby="map-title">
      <MapHeading />
      {timeline ? (
        <p className="map-lede" aria-live="polite">
          Leave <strong>{fmt(timeline.leave)}</strong> · {chancePercent}%{" "}
          {chanceLabel} · typical arrival{" "}
          <strong>{fmt(timeline.arriveP50)}</strong>, 9 in 10 by{" "}
          <strong>{fmt(timeline.arriveP90)}</strong>
          {preliminary && <span className="map-prelim"> · preliminary</span>}
        </p>
      ) : (
        <p className="map-lede" aria-live="polite">
          No departure meets your target for this deadline, so no journey is
          highlighted. The route is shown for reference.
        </p>
      )}
      <svg
        className="route-map"
        viewBox={`0 0 ${G.width} ${HEIGHT}`}
        role="img"
        aria-label={summary}
      >
        {/* Uncertainty lives in the wait and the whole ride, not at one stop. */}
        {timeline && (
          <path
            className="map-uncertainty"
            d={layout.path}
            aria-hidden="true"
          />
        )}

        {/* Walks */}
        <g
          className={timeline ? "map-walk" : "map-walk muted"}
          aria-hidden="true"
        >
          <line x1={50} y1={origin.y} x2={origin.x - 10} y2={origin.y} />
          <line x1={end.x + 10} y1={end.y} x2={END_X} y2={end.y} />
          <circle className="map-endpoint" cx={50} cy={origin.y} r={7} />
          <circle className="map-endpoint" cx={END_X} cy={end.y} r={7} />
          <text x={50} y={origin.y - 14} textAnchor="middle">
            Start
          </text>
          <text x={74} y={origin.y + 22} textAnchor="middle">
            Walk {walkTo} min
          </text>
          <text x={(end.x + END_X) / 2} y={end.y + 20} textAnchor="middle">
            Walk {walkFrom} min
          </text>
          <text x={END_X} y={end.y - 14} textAnchor="middle">
            Destination
          </text>
        </g>

        {/* Bus 29 */}
        <path
          className={timeline ? "map-route active" : "map-route"}
          d={layout.path}
          aria-hidden="true"
        />
        <g aria-hidden="true">
          {points.map((p, i) => {
            const terminal = i === 0 || i === points.length - 1;
            const lines = wrapLabel(stops[i].name, 11);
            return (
              <g key={stops[i].naptan_id + i}>
                {terminal ? (
                  <circle className="map-interchange" cx={p.x} cy={p.y} r={9} />
                ) : (
                  <line
                    className="map-tick"
                    x1={p.x}
                    y1={p.y}
                    x2={p.x}
                    y2={p.y - 11}
                  />
                )}
                {lines.map((line, j) => (
                  <text
                    key={j}
                    className={terminal ? "map-stop terminal" : "map-stop"}
                    x={p.x}
                    y={p.y - 18 - (lines.length - 1 - j) * 16}
                    textAnchor="middle"
                  >
                    {line}
                  </text>
                ))}
              </g>
            );
          })}
        </g>

        {timeline && (
          <g className="map-callouts" aria-hidden="true">
            <circle
              className="map-wait-halo"
              cx={origin.x}
              cy={origin.y}
              r={17}
            />
            <text
              x={10}
              y={origin.y + 42}
              textAnchor="start"
              className="strong"
            >
              Leave {fmt(timeline.leave)}
            </text>
            <text
              x={origin.x - 4}
              y={origin.y + 38}
              textAnchor="start"
              className="accent"
            >
              At stop ~{fmt(timeline.atStop)}
            </text>
            <text
              x={origin.x - 4}
              y={origin.y + 53}
              textAnchor="start"
              className="accent small"
            >
              wait varies
            </text>
            <text
              x={END_X - 14}
              y={end.y + 40}
              textAnchor="middle"
              className="strong"
            >
              {fmt(timeline.arriveP50)}–{fmt(timeline.arriveP90)}
            </text>
            <text
              x={END_X - 14}
              y={end.y + 54}
              textAnchor="middle"
              className="small"
            >
              p50–p90
            </text>
          </g>
        )}
      </svg>

      <p className="map-caption">
        <Icon name="info" size={15} />
        <span>
          Schematic, not to scale. Our recordings time whole trips from{" "}
          {stops[0].name} to {stops.at(-1)!.name}, inferred from TfL
          predictions, so delays at individual stops are not measured.
          {timeline &&
            " The shaded band marks where the uncertainty lives: the wait at the stop and the ride as a whole."}
        </span>
      </p>

      <details className="data-table">
        <summary>View the journey as a table</summary>
        {timeline && (
          <table>
            <caption>
              Selected departure, {fmt(timeline.leave)}. Times are estimates
              from replayed recorded trips.
            </caption>
            <thead>
              <tr>
                <th scope="col">Leg</th>
                <th scope="col">Typical (p50)</th>
                <th scope="col">Slower (p90)</th>
              </tr>
            </thead>
            <tbody>
              <tr>
                <th scope="row">Walk to {stops[0].name}</th>
                <td colSpan={2}>
                  {walkTo} min, at the stop about {fmt(timeline.atStop)}
                </td>
              </tr>
              <tr>
                <th scope="row">Wait and ride bus 29</th>
                <td>{timeline.waitRideMin} min</td>
                <td>{timeline.waitRideMin + timeline.spreadMin} min</td>
              </tr>
              <tr>
                <th scope="row">Walk from {stops.at(-1)!.name}</th>
                <td colSpan={2}>{walkFrom} min</td>
              </tr>
              <tr>
                <th scope="row">Arrive</th>
                <td>{fmt(timeline.arriveP50)}</td>
                <td>
                  {fmt(timeline.arriveP90)} ({slackLabel(timeline.slackP90Min)})
                </td>
              </tr>
            </tbody>
          </table>
        )}
        <table>
          <caption>Stops on bus 29, in order</caption>
          <thead>
            <tr>
              <th scope="col">#</th>
              <th scope="col">Stop</th>
            </tr>
          </thead>
          <tbody>
            {stops.map((stop, i) => (
              <tr key={stop.naptan_id + i}>
                <td>{i + 1}</td>
                <td>
                  {stop.name}
                  {i === 0
                    ? " (board)"
                    : i === stops.length - 1
                      ? " (alight)"
                      : ""}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </details>
    </section>
  );
}

function MapHeading() {
  return (
    <>
      <div className="section-top">
        <span className="eyebrow">04 / YOUR JOURNEY, MAPPED</span>
        <Icon name="map" size={19} />
      </div>
      <h2 id="map-title">Where the time goes</h2>
    </>
  );
}
