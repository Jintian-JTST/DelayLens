"""Turn a database snapshot and raw backups into M's segment CSV and coverage.

Runs without a database: it reads the gzip snapshot written by
``python -m ingest.admin snapshot`` and, optionally, the raw backup directory.
Times are prediction-derived estimates, never measured arrivals.
"""

from __future__ import annotations

import argparse
import csv
import gzip
import json
import os
from collections import Counter, defaultdict
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from .common import atomic_json, stable_id

PROJECT = Path(__file__).resolve().parents[2]
NEAR_STOP = "near_stop_prediction"
SOURCE = "tfl_live_recording"
# PLAN section 3.5 minimum fields, in M's order; extra traceability columns follow.
CSV_FIELDS = (
    "segment_id", "route_id", "vehicle_id", "origin_at", "destination_at",
    "travel_seconds", "inference_method", "quality", "source",
)
TRACE_FIELDS = (
    "line_id", "direction", "origin_method", "destination_method",
    "origin_episode_started_at", "destination_episode_started_at",
)
# Usable-run tiers from PLAN section 4; counts per local clock hour are indicative only.
TIERS = ((15, "ok"), (5, "low_data"), (0, "insufficient_data"))


def utc(value: str) -> datetime:
    result = datetime.fromisoformat(value)
    if result.tzinfo is None:
        raise ValueError("Naive timestamp")
    return result.astimezone(UTC)


def london():
    from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

    try:
        return ZoneInfo("Europe/London")
    except ZoneInfoNotFoundError as exc:
        raise RuntimeError("Europe/London time zone data missing; on Windows run via `uv run` "
                           "or install tzdata") from exc


def read_snapshot(path: Path) -> dict:
    with gzip.open(path, "rt", encoding="utf-8") as handle:
        snapshot = json.load(handle)
    if snapshot.get("format_version") != 1 or not isinstance(snapshot.get("segments"), list):
        raise ValueError("Unsupported snapshot")
    return snapshot


def segment_rows(segments: list[dict], route_ids: set[str] | None = None) -> tuple[list[dict], Counter]:
    """Map get_segments rows to CSV rows; only two near-stop endpoints are `estimated`."""
    excluded: Counter[str] = Counter()
    rows: dict[str, dict] = {}
    for segment in segments:
        if route_ids and segment["route_id"] not in route_ids:
            continue
        origin = utc(segment["origin_observed_at"])
        destination = utc(segment["destination_observed_at"])
        if destination <= origin:
            excluded["non_positive_duration"] += 1
            continue
        episode = utc(segment["origin_episode_started_at"])
        # Documented stable trip key: (route_id, vehicle_id, origin_episode_started_at).
        segment_id = stable_id("seg", segment["route_id"], segment["vehicle_id"], episode.isoformat())
        if segment_id in rows:
            excluded["duplicate_trip_key"] += 1
            continue
        methods = (segment["origin_method"], segment["destination_method"])
        rows[segment_id] = {
            "segment_id": segment_id,
            "route_id": segment["route_id"],
            "vehicle_id": segment["vehicle_id"],
            "origin_at": origin.isoformat(),
            "destination_at": destination.isoformat(),
            "travel_seconds": round((destination - origin).total_seconds()),
            "inference_method": methods[0] if methods[0] == methods[1] else "/".join(methods),
            # Disappearance-based endpoints stay inspectable but are not model evidence.
            "quality": "estimated" if methods == (NEAR_STOP, NEAR_STOP) else "uncertain",
            "source": SOURCE,
            "line_id": segment.get("line_id", ""),
            "direction": segment.get("direction", ""),
            "origin_method": methods[0],
            "destination_method": methods[1],
            "origin_episode_started_at": episode.isoformat(),
            "destination_episode_started_at": utc(segment["destination_episode_started_at"]).isoformat(),
        }
    ordered = sorted(rows.values(), key=lambda row: (row["route_id"], row["origin_at"], row["segment_id"]))
    return ordered, excluded


def backup_poll_times(backup_dir: Path) -> list[datetime]:
    """Successful poll times from pending and archived raw backups."""
    times = []
    for path in backup_dir.rglob("*.jsonl.gz"):
        with gzip.open(path, "rt", encoding="utf-8") as handle:
            batch = json.loads(handle.readline())
        if batch.get("format_version") != 1:
            raise ValueError(f"Unsupported backup: {path.name}")
        times.append(utc(batch["polled_at"]))
    return sorted(set(times))


def coverage_intervals(times: list[datetime], max_gap: timedelta) -> list[dict]:
    """Closed UTC intervals of continuous polling; a gap above max_gap starts a new one."""
    intervals: list[dict] = []
    for moment in times:
        if intervals and moment - intervals[-1]["end"] <= max_gap:
            intervals[-1]["end"] = moment
            intervals[-1]["polls"] += 1
        else:
            intervals.append({"start": moment, "end": moment, "polls": 1})
    return [{"start": item["start"].isoformat(), "end": item["end"].isoformat(), "polls": item["polls"]}
            for item in intervals]


def tier(usable: int) -> str:
    return next(name for minimum, name in TIERS if usable >= minimum)


def hourly_support(rows: list[dict]) -> list[dict]:
    """Usable/uncertain runs per route and Europe/London clock hour of origin.

    The hour keeps its UTC offset, so the repeated 01:00 on a clock change stays
    two separate hours instead of being pooled.
    """
    zone = london()
    groups: dict[tuple[str, str], dict] = defaultdict(lambda: {"estimated": 0, "uncertain": 0, "vehicles": set()})
    for row in rows:
        local = utc(row["origin_at"]).astimezone(zone).replace(minute=0, second=0, microsecond=0)
        group = groups[(row["route_id"], local.isoformat())]
        if row["quality"] == "estimated":
            group["estimated"] += 1
            group["vehicles"].add(row["vehicle_id"])
        else:
            group["uncertain"] += 1
    return [{"route_id": route_id, "local_hour": hour, "usable_runs": group["estimated"],
             "uncertain_runs": group["uncertain"], "distinct_vehicles": len(group["vehicles"]),
             "tier": tier(group["estimated"])}
            for (route_id, hour), group in sorted(groups.items(), key=lambda item: (item[0][0], utc(item[0][1])))]


def write_csv(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    with temporary.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=CSV_FIELDS + TRACE_FIELDS)
        writer.writeheader()
        writer.writerows(rows)
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, path)


def export(snapshot_path: Path, out_dir: Path, backup_dir: Path | None = None,
           route_ids: set[str] | None = None, max_gap_seconds: float = 90) -> dict:
    snapshot = read_snapshot(snapshot_path)
    rows, excluded = segment_rows(snapshot["segments"], route_ids)
    write_csv(out_dir / "segments.csv", rows)
    counts = Counter((row["route_id"], row["quality"]) for row in rows)
    summary: dict[str, Any] = {
        "snapshot_generated_at": snapshot.get("generated_at"),
        "provenance": "TfL prediction-derived estimates, not measured arrivals",
        "routes": {route: {"estimated": counts[(route, "estimated")], "uncertain": counts[(route, "uncertain")]}
                   for route in sorted({row["route_id"] for row in rows})},
        "excluded": dict(excluded),
        "hourly_support": hourly_support(rows),
    }
    if backup_dir is not None:
        times = backup_poll_times(backup_dir)
        intervals = coverage_intervals(times, timedelta(seconds=max_gap_seconds))
        atomic_json(out_dir / "coverage.json", {
            "max_gap_seconds": max_gap_seconds,
            "first_poll": times[0].isoformat() if times else None,
            "last_poll": times[-1].isoformat() if times else None,
            "successful_polls": len(times),
            "intervals": intervals,
        })
        summary["coverage_intervals"] = len(intervals)
    atomic_json(out_dir / "summary.json", summary)
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--snapshot", type=Path, default=PROJECT / ".local" / "delaylens-snapshot.json.gz")
    parser.add_argument("--backups", type=Path, help="Raw backup directory (RAW_BACKUP_DIR) for coverage")
    parser.add_argument("--out-dir", type=Path, default=PROJECT / ".local" / "handoff")
    parser.add_argument("--route-id", action="append", help="Limit to this route; repeatable")
    parser.add_argument("--max-gap-seconds", type=float, default=90)
    args = parser.parse_args()
    summary = export(args.snapshot, args.out_dir, args.backups,
                     set(args.route_id) if args.route_id else None, args.max_gap_seconds)
    print(json.dumps({key: summary[key] for key in ("routes", "excluded")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
