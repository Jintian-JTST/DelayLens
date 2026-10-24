"""Offline snapshot mode: build a db.Snapshot from a frozen folder, with no database.

The folder is what `tools/export_db_snapshot.py` writes: `summary.json` and
`poll_times.csv`, plus one subfolder per route holding `segments.csv`,
`origin_events.csv` and `coverage.json`. Set SNAPSHOT_DIR to it (PLAN.md section 9:
"snapshot mode needs no Tiger Data"). Nothing here touches the network or any secret.
"""

import csv
import json
from datetime import UTC, datetime
from pathlib import Path

from app import db
from app.schemas import Stats


def _when(value: str) -> datetime:
    parsed = datetime.fromisoformat(value)
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)


def _read_csv(path: Path, columns: list[str]) -> list[dict[str, str]]:
    if not path.is_file():
        raise ValueError(f"snapshot file missing: {path.name}")
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        if reader.fieldnames is None or any(c not in reader.fieldnames for c in columns):
            raise ValueError(f"{path.name}: expected columns {', '.join(columns)}")
        return list(reader)


def load_snapshot_dir(directory: str | Path) -> db.Snapshot:
    root = Path(directory)
    summary_path = root / "summary.json"
    if not summary_path.is_file():
        raise ValueError(f"SNAPSHOT_DIR has no summary.json: {root.name}")
    try:
        summary = json.loads(summary_path.read_text(encoding="utf-8"))
        refreshed_at = _when(summary["snapshot_refreshed_at_utc"])
        poll_times = sorted(
            _when(row["polled_at"]) for row in _read_csv(root / "poll_times.csv", ["polled_at"])
        )

        segments: dict[str, list[db.Segment]] = {}
        origin_events: dict[str, list[db.OriginEvent]] = {}
        coverage: dict[str, db.Coverage] = {}
        for folder in sorted(p for p in root.iterdir() if p.is_dir()):
            route_id = folder.name
            segments[route_id] = sorted(
                (
                    db.Segment(
                        vehicle_id=row["vehicle_id"],
                        origin_observed_at=_when(row["origin_observed_at"]),
                        destination_observed_at=_when(row["destination_observed_at"]),
                        ride_seconds=float(row["ride_seconds"]),
                        origin_episode_started_at=_when(row["origin_episode_started_at"]),
                    )
                    for row in _read_csv(
                        folder / "segments.csv",
                        ["vehicle_id", "origin_observed_at", "destination_observed_at",
                         "ride_seconds", "origin_episode_started_at"],
                    )
                ),
                key=lambda s: s.origin_observed_at,
            )
            origin_events[route_id] = sorted(
                (
                    db.OriginEvent(
                        vehicle_id=row["vehicle_id"],
                        episode_started_at=_when(row["episode_started_at"]),
                        observed_at=_when(row["observed_at"]),
                    )
                    for row in _read_csv(
                        folder / "origin_events.csv",
                        ["vehicle_id", "episode_started_at", "observed_at"],
                    )
                ),
                key=lambda e: e.observed_at,
            )
            cov = json.loads((folder / "coverage.json").read_text(encoding="utf-8"))
            coverage[route_id] = db.Coverage(
                int(cov["trips_observed"]), [_when(h) for h in cov["hours_covered"]]
            )
    except (KeyError, TypeError, ValueError, OSError) as exc:
        # Name the problem, never file contents.
        raise ValueError(f"SNAPSHOT_DIR is not a valid snapshot ({type(exc).__name__}: {exc})") from None
    if not segments:
        raise ValueError("SNAPSHOT_DIR has no route folders")

    stamp = refreshed_at.strftime("%d %b %H:%M")
    return db.Snapshot(
        segments=segments,
        coverage=coverage,
        origin_events=origin_events,
        poll_times=poll_times,
        # Row and chunk counts are database facts the frozen folder does not hold.
        stats=Stats(
            rows=0,
            chunks=0,
            compression_ratio=None,
            first_polled_at=poll_times[0] if poll_times else None,
            last_polled_at=poll_times[-1] if poll_times else None,
        ),
        refreshed_at=refreshed_at,
        source_label=f"Offline snapshot frozen {stamp} UTC; not live data.",
    )
