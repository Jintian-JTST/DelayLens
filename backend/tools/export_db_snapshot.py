"""Freeze what the API sees in Tiger Data into a portable folder (read-only).

Uses app.db.load_snapshot, the same loader the API cache uses, so the export
matches the data behind /api/departure-curve at that moment. Writes per route:
segments.csv, origin_events.csv and coverage.json, plus a shared
poll_times.csv and summary.json. Never writes or prints DATABASE_URL.

Run from backend/:
    python -m tools.export_db_snapshot --out ../docs/evidence/<folder> --route-filter bus-29
"""

import argparse
import csv
import json
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

from app import db

SEGMENT_COLUMNS = [
    "route_id", "vehicle_id", "origin_observed_at", "destination_observed_at",
    "ride_seconds", "origin_episode_started_at",
]
ORIGIN_EVENT_COLUMNS = ["route_id", "vehicle_id", "episode_started_at", "observed_at"]


def _write_csv(path: Path, header: list[str], rows: list[list]) -> None:
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f, lineterminator="\n")
        writer.writerow(header)
        writer.writerows(rows)


def export(snapshot: db.Snapshot, out_dir: Path, route_filter: str = "") -> dict:
    """Write the snapshot's routes matching `route_filter` (substring) to `out_dir`."""
    out_dir.mkdir(parents=True, exist_ok=True)
    route_ids = sorted(
        r for r in {*snapshot.segments, *snapshot.origin_events, *snapshot.coverage}
        if route_filter in r
    )
    polls = sorted(snapshot.poll_times)
    _write_csv(out_dir / "poll_times.csv", ["polled_at"], [[t.isoformat()] for t in polls])
    summary = {
        "snapshot_refreshed_at_utc": snapshot.refreshed_at.isoformat(),
        "source": "Tiger Data views via backend/app/db.load_snapshot (read-only)",
        "poll_count": len(polls),
        "first_poll_utc": polls[0].isoformat() if polls else None,
        "last_poll_utc": polls[-1].isoformat() if polls else None,
        "routes": {},
    }
    for route_id in route_ids:
        folder = out_dir / route_id
        folder.mkdir(exist_ok=True)
        segments = sorted(snapshot.segments.get(route_id, []), key=lambda s: s.origin_observed_at)
        _write_csv(folder / "segments.csv", SEGMENT_COLUMNS, [
            [route_id, s.vehicle_id, s.origin_observed_at.isoformat(),
             s.destination_observed_at.isoformat(), s.ride_seconds,
             s.origin_episode_started_at.isoformat()]
            for s in segments
        ])
        events = sorted(snapshot.origin_events.get(route_id, []), key=lambda e: e.observed_at)
        _write_csv(folder / "origin_events.csv", ORIGIN_EVENT_COLUMNS, [
            [route_id, e.vehicle_id, e.episode_started_at.isoformat(), e.observed_at.isoformat()]
            for e in events
        ])
        cov = snapshot.coverage.get(route_id)
        coverage = (
            {"trips_observed": cov.trips_observed,
             "hours_covered": [h.isoformat() for h in cov.hours_covered]}
            if cov else None
        )
        (folder / "coverage.json").write_text(
            json.dumps(coverage, indent=2) + "\n", encoding="utf-8", newline="\n"
        )
        summary["routes"][route_id] = {
            "segments": len(segments),
            "origin_events": len(events),
            "first_origin_utc": segments[0].origin_observed_at.isoformat() if segments else None,
            "last_origin_utc": segments[-1].origin_observed_at.isoformat() if segments else None,
            "coverage": coverage,
        }
    (out_dir / "summary.json").write_text(
        json.dumps(summary, indent=2) + "\n", encoding="utf-8", newline="\n"
    )
    return summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--route-filter", default="", help="route_id substring, e.g. bus-29")
    args = parser.parse_args(argv)
    load_dotenv()
    url = os.getenv("DATABASE_URL", "")
    if not url or "user:password@host" in url:
        print("DATABASE_URL is not configured (see backend/.env.example)", file=sys.stderr)
        return 2
    summary = export(db.load_snapshot(url), args.out, args.route_filter)
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
