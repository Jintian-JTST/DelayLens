import { useEffect, useRef, useState } from "react";
import type { CurvePoint } from "../api";
import { curveSegments } from "../chart";
import { timeLabel, type Clock } from "../time";

interface Props {
  points: CurvePoint[];
  recommended: CurvePoint | null;
  selected: CurvePoint | null;
  tolerance: number;
  clock: Clock;
  windowStart: string;
  windowEnd: string;
}

export default function DepartureCurve({
  points,
  recommended,
  selected,
  tolerance,
  clock,
  windowStart,
  windowEnd,
}: Props) {
  const [hover, setHover] = useState<number | null>(null);
  const svg = useRef<SVGSVGElement>(null);
  const [width, setWidth] = useState(780);
  useEffect(() => {
    const observer = new ResizeObserver(([entry]) =>
      setWidth(Math.max(240, entry.contentRect.width)),
    );
    if (svg.current) observer.observe(svg.current);
    return () => observer.disconnect();
  }, []);
  const height = width < 500 ? 260 : 292;
  const left = 43,
    right = 23,
    top = 25,
    bottom = 42;
  const first = Date.parse(windowStart);
  const last = Date.parse(windowEnd);
  const x = (iso: string) =>
    left +
    ((Date.parse(iso) - first) / Math.max(1, last - first)) *
      (width - left - right);
  const y = (p: number) => top + (1 - p) * (height - top - bottom);
  const paths = curveSegments(points).map((segment) => {
    const line = segment
      .map((p, i) => `${i ? "L" : "M"}${x(p.depart_at)},${y(p.p_on_time)}`)
      .join(" ");
    const band =
      segment
        .map((p, i) => `${i ? "L" : "M"}${x(p.depart_at)},${y(p.ci[1])}`)
        .join(" ") +
      [...segment]
        .reverse()
        .map((p) => `L${x(p.depart_at)},${y(p.ci[0])}`)
        .join(" ") +
      "Z";
    return { segment, line, band };
  });
  // Without a recommendation nothing is pre-selected: highlighting the first
  // point (the earliest departure, often 100%) would read as advice.
  const focus =
    hover === null
      ? (selected ?? recommended ?? null)
      : points[Math.min(hover, points.length - 1)];
  const ticks = [0, 0.25, 0.5, 0.75, 1];

  return (
    <>
      <div className="chart-readout" aria-live="polite" aria-atomic="true">
        <span>
          {focus ? (
            <>
              At <strong>{timeLabel(focus.depart_at, clock)}</strong> ·{" "}
              {focus.n_trips} trips
            </>
          ) : (
            "Explore the departure curve"
          )}
        </span>
        <span>
          {focus ? (
            <>
              <strong>{Math.round(focus.p_on_time * 100)}%</strong> estimated
              on-time probability
            </>
          ) : (
            "Earlier departures give you more room"
          )}
        </span>
      </div>
      <svg
        ref={svg}
        className="curve-svg"
        viewBox={`0 0 ${width} ${height}`}
        role="group"
        aria-roledescription="interactive departure chart"
        aria-label="Chance of arriving on time by departure time"
        aria-describedby="chart-description"
        tabIndex={0}
        onPointerMove={(event) => {
          const rect = event.currentTarget.getBoundingClientRect();
          const position = ((event.clientX - rect.left) / rect.width) * width;
          const target =
            first +
            Math.max(
              0,
              Math.min(1, (position - left) / (width - left - right)),
            ) *
              (last - first);
          setHover(
            points.reduce(
              (nearest, point, index) =>
                Math.abs(Date.parse(point.depart_at) - target) <
                Math.abs(Date.parse(points[nearest].depart_at) - target)
                  ? index
                  : nearest,
              0,
            ),
          );
        }}
        onPointerLeave={() => setHover(null)}
        onKeyDown={(event) => {
          if (!["ArrowRight", "ArrowLeft", "Home", "End"].includes(event.key))
            return;
          event.preventDefault();
          const current =
            hover ??
            Math.max(
              0,
              points.findIndex((p) => p.depart_at === recommended?.depart_at),
            );
          setHover(
            event.key === "Home"
              ? 0
              : event.key === "End"
                ? points.length - 1
                : Math.min(
                    points.length - 1,
                    Math.max(
                      0,
                      current + (event.key === "ArrowRight" ? 1 : -1),
                    ),
                  ),
          );
        }}
      >
        <title>Departure time and estimated probability of arriving on time</title>
        <desc id="chart-description">
          The shaded area is the 90% uncertainty band. Use left and right arrow
          keys to explore each departure. Exact values are available in the data
          table.
        </desc>
        <defs>
          <linearGradient id="curve-fill" x1="0" x2="0" y1="0" y2="1">
            <stop stopColor="#2f6fe4" stopOpacity=".10" />
            <stop offset="1" stopColor="#2f6fe4" stopOpacity=".01" />
          </linearGradient>
        </defs>
        {ticks.map((p) => (
          <g key={p}>
            <line
              x1={left}
              x2={width - right}
              y1={y(p)}
              y2={y(p)}
              stroke="#e9ebed"
              strokeDasharray={p === 0 ? undefined : "3 5"}
            />
            <text
              x={left - 12}
              y={y(p) + 4}
              textAnchor="end"
              className="axis-text"
            >
              {p * 100}%
            </text>
          </g>
        ))}
        {paths.map(({ segment, line, band }) => (
          <g key={segment[0].depart_at}>
            <path
              d={`${line}L${x(segment.at(-1)!.depart_at)},${y(0)}L${x(segment[0].depart_at)},${y(0)}Z`}
              fill="url(#curve-fill)"
            />
            <path d={band} fill="#a0b5d8" opacity=".27" />
          </g>
        ))}
        <line
          x1={left}
          x2={width - right}
          y1={y(1 - tolerance)}
          y2={y(1 - tolerance)}
          stroke="#7fa6ee"
          strokeDasharray="5 5"
        />
        {paths.map(({ segment, line }) => (
          <g key={segment[0].depart_at}>
            <path
              className="probability-line"
              d={line}
              stroke="#2f6fe4"
              strokeWidth="3"
              fill="none"
              strokeLinejoin="round"
              strokeLinecap="round"
            />
            {segment.length === 1 && (
              <>
                <line
                  x1={x(segment[0].depart_at)}
                  x2={x(segment[0].depart_at)}
                  y1={y(segment[0].ci[0])}
                  y2={y(segment[0].ci[1])}
                  stroke="#a0b5d8"
                  strokeWidth="3"
                />
                <circle
                  cx={x(segment[0].depart_at)}
                  cy={y(segment[0].p_on_time)}
                  r="3"
                  fill="#2f6fe4"
                />
              </>
            )}
          </g>
        ))}
        {recommended && (
          <line
            x1={x(recommended.depart_at)}
            x2={x(recommended.depart_at)}
            y1={top}
            y2={height - bottom}
            stroke="#2f6fe4"
            strokeDasharray="4 5"
            opacity=".7"
          />
        )}
        {focus && (
          <g>
            <line
              x1={x(focus.depart_at)}
              x2={x(focus.depart_at)}
              y1={y(focus.p_on_time)}
              y2={height - bottom}
              stroke="#8597b5"
              strokeDasharray="2 4"
            />
            <circle
              cx={x(focus.depart_at)}
              cy={y(focus.p_on_time)}
              r="8"
              fill="#fff"
              stroke="#2f6fe4"
              strokeWidth="3"
            />
            <circle
              cx={x(focus.depart_at)}
              cy={y(focus.p_on_time)}
              r="3"
              fill="#2f6fe4"
            />
          </g>
        )}
        {(width < 500 ? [0, 1 / 3, 2 / 3, 1] : [0, 0.2, 0.4, 0.6, 0.8, 1]).map(
          (fraction) => {
            const iso = new Date(
              first + fraction * (last - first),
            ).toISOString();
            return (
              <text
                key={fraction}
                x={x(iso)}
                y={height - 16}
                textAnchor="middle"
                className="axis-text"
              >
                {timeLabel(iso, clock)}
              </text>
            );
          },
        )}
      </svg>
      <div className="chart-key">
        <span>
          <i className="key-line" />
          Estimated on-time probability
        </span>
        <span>
          <i className="key-band" />
          90% uncertainty band
        </span>
        <span>
          <i className="key-target" />
          Your target
        </span>
      </div>
      <details className="data-table">
        <summary>View departure data</summary>
        <div className="table-scroll">
          <table>
            <caption>Departure predictions and uncertainty</caption>
            <thead>
              <tr>
                <th>Leave at</th>
                <th>On time</th>
                <th>90% band</th>
                <th>Trips</th>
              </tr>
            </thead>
            <tbody>
              {points.map((p) => (
                <tr key={p.depart_at}>
                  <td>{timeLabel(p.depart_at, clock)}</td>
                  <td>{Math.round(p.p_on_time * 100)}%</td>
                  <td>
                    {Math.round(p.ci[0] * 100)}–{Math.round(p.ci[1] * 100)}%
                  </td>
                  <td>{p.n_trips}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </details>
    </>
  );
}
