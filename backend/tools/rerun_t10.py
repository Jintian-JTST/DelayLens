"""Rerun the T10 check (backtest and demo numbers) on frozen snapshot folders (read-only).

Uses the API's own loaders, model and blocked hold-out backtest, so the numbers match
/api/calibration and /api/departure-curve in snapshot mode. For each folder and route it
prints usable runs per London hour, the Brier score, outcome/run counts and calibration
bins. For the demo route it also prints the advice for the Saturday 17:00 and 15:30
deadlines (walks 5/5, 10% tolerance, ±60-minute window). Pass the old folder first and the
new one second to compare them. Relative paths are taken from the repository root.

Run from backend/:
    uv run --locked python -m tools.rerun_t10 docs/evidence/bus29-db-final-20261024T202558Z [NEW_FOLDER] \
        [--standalone docs/evidence/<standalone handoff>]

On the 20:25Z snapshot this reproduces Brier 0.1296 (Mornington Crescent) and 0.1318
(Finsbury Park), and Sat 17:00 -> leave 16:22 at p=0.9174.
"""

import argparse
import sys
from collections import Counter
from datetime import datetime

from app import calibration, curves, model, snapshot_files

DEMO_ROUTE = "bus-29-outbound-mornington-crescent-tottenham-court-road"
# Demo deadlines on the recorded Saturday, London time: advice and the no-advice contrast.
DEMO_DEADLINES = ((17, 0), (15, 30))
DEMO_DATE = (2026, 10, 24)


def _london(epoch: float) -> datetime:
    return datetime.fromtimestamp(int(epoch), model.LONDON)


def _runs_by_hour(segments: model.Segments) -> str:
    # The autumn clock change repeats 01:00 in London. Keep both UTC offsets,
    # and the full date, so distinct recorded hours cannot collapse together.
    hours = Counter(
        _london(t).strftime("%Y-%m-%d %H:00 %Z (%z)") for t in segments.t_origin
    )
    return ", ".join(f"{hour}: {n}" for hour, n in sorted(hours.items()))


def _advice(segments: model.Segments, hour: int, minute: int) -> str:
    deadline = datetime(*DEMO_DATE, hour, minute, tzinfo=model.LONDON)
    curve = model.departure_curve(
        segments, deadline, walk_to_min=5, walk_from_min=5,
        tod_window_min=curves.TOD_WINDOW_MIN, n_boot=0,
    )
    advice = model.recommend(curve)
    ok = int((curve.status == "ok").sum())
    shown = (
        f"leave {_london(advice.depart_at):%H:%M} p={advice.p_on_time:.4f}"
        if advice.depart_at else advice.reason
    )
    return (
        f"Sat {hour:02d}:{minute:02d} London: {shown} "
        f"(up to {int(curve.n_trips.max())} runs, {ok}/{len(curve.status)} points ok)"
    )


def describe(folder: str) -> None:
    snap = snapshot_files.load_snapshot_dir(folder)
    print(f"\n== {folder}")
    print(f"frozen {snap.refreshed_at:%Y-%m-%d %H:%M} UTC, {len(snap.poll_times)} polls")
    for route_id in sorted(snap.segments):
        segments = curves.to_segments(
            snap.segments[route_id], snap.origin_events.get(route_id, []), snap.poll_times
        )
        cal = calibration.summarise(*calibration.backtest(segments))
        print(f"- {route_id}: {len(segments)} runs")
        print(f"  runs per London hour: {_runs_by_hour(segments)}")
        print(
            f"  backtest: {cal.calibration_status}, Brier {cal.brier_score}, "
            f"{cal.n_outcomes} outcomes, {cal.n_runs} runs"
        )
        for b in cal.bins:
            print(f"    predicted {b.predicted:.3f} observed {b.observed:.3f} (n={b.n})")
        if route_id == DEMO_ROUTE:
            for hour, minute in DEMO_DEADLINES:
                print(f"  {_advice(segments, hour, minute)}")


def describe_standalone(folder: str) -> None:
    segments, report = model.load_handoff(snapshot_files.resolve_snapshot_dir(folder))
    print(f"\n== standalone {folder}")
    print(f"{report.n_used}/{report.n_rows} rows used, {len(segments)} runs")
    print(f"runs per London hour: {_runs_by_hour(segments)}")
    for hour, minute in DEMO_DEADLINES:
        print(_advice(segments, hour, minute))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("snapshots", nargs="+", help="snapshot folders, old first")
    parser.add_argument("--standalone", action="append", default=[],
                        help="standalone handoff folder (segments.csv, route.json, ...)")
    args = parser.parse_args()
    try:
        for folder in args.snapshots:
            describe(folder)
        for folder in args.standalone:
            describe_standalone(folder)
    except (OSError, ValueError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
