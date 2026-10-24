"""Snapshot -> M's segment CSV, coverage intervals and hourly support, without a database."""

import csv
import gzip
import json
from datetime import UTC, datetime, timedelta

import pytest
from app.model import load_segments_csv
from ingest.export import coverage_intervals, export, segment_rows

ROUTE = "bus-29-outbound-finsbury-park-tottenham-court-road"


def segment(vehicle, origin, destination, origin_method="near_stop_prediction",
            destination_method="near_stop_prediction", episode=None):
    # Shape of `SELECT * FROM get_segments` as serialized by `ingest.admin snapshot`.
    return {
        "route_id": ROUTE, "vehicle_id": vehicle, "line_id": "29", "direction": "outbound",
        "origin_observed_at": origin, "destination_observed_at": destination,
        "origin_episode_started_at": episode or origin, "destination_episode_started_at": destination,
        "origin_method": origin_method, "destination_method": destination_method,
        "ride_seconds": (datetime.fromisoformat(destination) - datetime.fromisoformat(origin)).total_seconds(),
    }


# Values from the first real bus 29 matches on 2026-10-24.
SEGMENTS = [
    segment("LJ13FCY", "2026-10-24T14:06:14+00:00", "2026-10-24T14:47:05+00:00"),
    segment("LJ13FBO", "2026-10-24T14:12:01+00:00", "2026-10-24T14:48:23+00:00"),
    segment("LK66HCO", "2026-10-24T14:26:51.279835+00:00", "2026-10-24T15:09:49+00:00", origin_method="last_poll"),
]


def write_snapshot(path, segments):
    with gzip.open(path, "wt", encoding="utf-8") as handle:
        json.dump({"format_version": 1, "generated_at": "2026-10-24T15:20:00+00:00",
                   "routes": [], "segments": segments, "coverage": []}, handle)


def write_backup(directory, polled_at):
    directory.mkdir(parents=True, exist_ok=True)
    name = polled_at.strftime("%Y%m%dT%H%M%S") + ".jsonl.gz"
    with gzip.open(directory / name, "wt", encoding="utf-8") as handle:
        handle.write(json.dumps({"format_version": 1, "polled_at": polled_at.isoformat(), "rows": []}) + "\n")


def test_only_two_near_stop_endpoints_are_estimated():
    rows, excluded = segment_rows(SEGMENTS)
    assert [row["quality"] for row in rows] == ["estimated", "estimated", "uncertain"]
    assert rows[2]["inference_method"] == "last_poll/near_stop_prediction"
    assert [row["travel_seconds"] for row in rows] == [2451, 2182, 2578]
    assert not excluded


def test_segment_id_is_stable_across_timestamp_spelling():
    first, _ = segment_rows([SEGMENTS[0]])
    respelled = dict(SEGMENTS[0], origin_episode_started_at="2026-10-24T15:06:14+01:00")
    second, _ = segment_rows([respelled])
    assert first[0]["segment_id"] == second[0]["segment_id"]
    other, _ = segment_rows([SEGMENTS[1]])
    assert other[0]["segment_id"] != first[0]["segment_id"]


def test_duplicate_trip_key_and_bad_duration_are_counted_not_exported():
    later = dict(SEGMENTS[0], destination_observed_at="2026-10-24T14:59:00+00:00")
    backwards = segment("X1", "2026-10-24T14:10:00+00:00", "2026-10-24T14:09:00+00:00")
    rows, excluded = segment_rows([SEGMENTS[0], later, backwards])
    assert len(rows) == 1
    assert excluded == {"duplicate_trip_key": 1, "non_positive_duration": 1}


def test_csv_is_read_by_model_loader(tmp_path):
    snapshot = tmp_path / "snapshot.json.gz"
    write_snapshot(snapshot, SEGMENTS)
    summary = export(snapshot, tmp_path / "out")
    assert summary["routes"] == {ROUTE: {"estimated": 2, "uncertain": 1}}
    segments, report = load_segments_csv(tmp_path / "out" / "segments.csv", ROUTE)
    assert report.n_rows == 3 and report.n_used == 2
    assert report.excluded == {"not_estimated": 1}
    assert list(segments.vehicle_id) == ["LJ13FCY", "LJ13FBO"]
    with open(tmp_path / "out" / "segments.csv", newline="", encoding="utf-8") as handle:
        assert next(csv.reader(handle))[:9] == [
            "segment_id", "route_id", "vehicle_id", "origin_at", "destination_at",
            "travel_seconds", "inference_method", "quality", "source"]


def test_route_filter(tmp_path):
    other = dict(SEGMENTS[0], route_id="tube-victoria-outbound-brixton-oxford-circus")
    snapshot = tmp_path / "snapshot.json.gz"
    write_snapshot(snapshot, [SEGMENTS[0], other])
    summary = export(snapshot, tmp_path / "out", route_ids={ROUTE})
    assert list(summary["routes"]) == [ROUTE]


def test_coverage_splits_on_gaps_and_reads_pending_and_archive(tmp_path):
    start = datetime(2026, 10, 24, 13, 49, 34, tzinfo=UTC)
    for step in range(4):
        write_backup(tmp_path / "raw" / "archive" / "2026-10-24", start + timedelta(seconds=30 * step))
    resumed = start + timedelta(minutes=10)
    write_backup(tmp_path / "raw" / "pending", resumed)
    snapshot = tmp_path / "snapshot.json.gz"
    write_snapshot(snapshot, SEGMENTS)
    export(snapshot, tmp_path / "out", backup_dir=tmp_path / "raw")
    coverage = json.loads((tmp_path / "out" / "coverage.json").read_text(encoding="utf-8"))
    assert coverage["successful_polls"] == 5
    assert coverage["intervals"] == [
        {"start": start.isoformat(), "end": (start + timedelta(seconds=90)).isoformat(), "polls": 4},
        {"start": resumed.isoformat(), "end": resumed.isoformat(), "polls": 1},
    ]


def test_coverage_gap_threshold_is_inclusive():
    times = [datetime(2026, 10, 24, 14, tzinfo=UTC) + timedelta(seconds=s) for s in (0, 90, 181)]
    assert [item["polls"] for item in coverage_intervals(times, timedelta(seconds=90))] == [2, 1]


def test_hourly_support_keeps_repeated_clock_change_hour_separate(tmp_path):
    # 00:30Z and 01:30Z on 2026-10-25 are both 01:30 London time, before and after the change.
    early = [segment(f"A{i}", f"2026-10-25T00:{10 + i:02d}:00+00:00", f"2026-10-25T00:{30 + i:02d}:00+00:00")
             for i in range(5)]
    late = [segment("B1", "2026-10-25T01:30:00+00:00", "2026-10-25T01:50:00+00:00", origin_method="last_poll")]
    snapshot = tmp_path / "snapshot.json.gz"
    write_snapshot(snapshot, early + late)
    hours = export(snapshot, tmp_path / "out")["hourly_support"]
    assert [(h["local_hour"], h["usable_runs"], h["uncertain_runs"], h["tier"]) for h in hours] == [
        ("2026-10-25T01:00:00+01:00", 5, 0, "low_data"),
        ("2026-10-25T01:00:00+00:00", 0, 1, "insufficient_data"),
    ]


def test_unsupported_snapshot_is_rejected(tmp_path):
    path = tmp_path / "snapshot.json.gz"
    with gzip.open(path, "wt", encoding="utf-8") as handle:
        json.dump({"format_version": 2, "segments": []}, handle)
    with pytest.raises(ValueError, match="Unsupported snapshot"):
        export(path, tmp_path / "out")
