"""Offline snapshot mode: the API runs from a frozen folder with no database."""

import json
from pathlib import Path

import psycopg
import pytest
from fastapi.testclient import TestClient

from app import main, snapshot_files

FROZEN = Path(__file__).resolve().parents[2] / "docs" / "evidence" / "bus29-db-snapshot-20261024T1655Z"
MORNINGTON = "bus-29-outbound-mornington-crescent-tottenham-court-road"
FINSBURY = "bus-29-outbound-finsbury-park-tottenham-court-road"

SEGMENT_HEADER = "route_id,vehicle_id,origin_observed_at,destination_observed_at,ride_seconds,origin_episode_started_at\n"
EVENT_HEADER = "route_id,vehicle_id,episode_started_at,observed_at\n"


def _mini_snapshot(root: Path) -> Path:
    """One route, one segment, one unconfirmed departure; rows written out of order."""
    route = root / "r1"
    route.mkdir(parents=True)
    (root / "summary.json").write_text(
        json.dumps({"snapshot_refreshed_at_utc": "2026-10-24T16:55:34+00:00"}), encoding="utf-8"
    )
    (root / "poll_times.csv").write_text(
        "polled_at\n2026-10-24T13:50:00+00:00\n2026-10-24T13:49:00+00:00\n", encoding="utf-8"
    )
    (route / "segments.csv").write_text(
        SEGMENT_HEADER
        + "r1,B,2026-10-24T14:10:00+00:00,2026-10-24T14:25:00+00:00,900.0,2026-10-24T13:49:00+00:00\n"
        + "r1,A,2026-10-24T14:00:00+00:00,2026-10-24T14:14:00+00:00,840.0,2026-10-24T13:49:00+00:00\n",
        encoding="utf-8",
    )
    (route / "origin_events.csv").write_text(
        EVENT_HEADER + "r1,C,2026-10-24T13:49:00+00:00,2026-10-24T14:20:00+00:00\n", encoding="utf-8"
    )
    (route / "coverage.json").write_text(
        json.dumps({"trips_observed": 2, "hours_covered": ["2026-10-24T14:00:00+00:00"]}), encoding="utf-8"
    )
    return root


def test_loads_the_frozen_bus_29_folder():
    snapshot = snapshot_files.load_snapshot_dir(FROZEN)
    assert len(snapshot.segments[MORNINGTON]) == 26
    assert len(snapshot.segments[FINSBURY]) == 18
    assert len(snapshot.origin_events[MORNINGTON]) == 31
    assert snapshot.coverage[MORNINGTON].trips_observed == 26
    assert len(snapshot.poll_times) == 373
    assert snapshot.refreshed_at.isoformat().startswith("2026-10-24T16:55:34")
    assert snapshot.source_label == "Offline snapshot frozen 24 Oct 16:55 UTC; not live data."


def test_parses_types_timezones_and_sorts(tmp_path):
    snapshot = snapshot_files.load_snapshot_dir(_mini_snapshot(tmp_path))
    segments = snapshot.segments["r1"]
    assert [s.vehicle_id for s in segments] == ["A", "B"]  # sorted by origin time
    assert segments[0].ride_seconds == 840.0
    assert segments[0].origin_observed_at.utcoffset().total_seconds() == 0
    assert [t.minute for t in snapshot.poll_times] == [49, 50]
    assert snapshot.origin_events["r1"][0].vehicle_id == "C"
    assert snapshot.coverage["r1"].hours_covered[0].hour == 14
    assert snapshot.stats.first_polled_at == snapshot.poll_times[0]


@pytest.mark.parametrize("breakage", ["no_summary", "no_segments", "bad_number", "missing_column", "no_routes"])
def test_a_bad_folder_raises_a_clear_error(tmp_path, breakage):
    root = _mini_snapshot(tmp_path)
    if breakage == "no_summary":
        (root / "summary.json").unlink()
    elif breakage == "no_segments":
        (root / "r1" / "segments.csv").unlink()
    elif breakage == "bad_number":
        path = root / "r1" / "segments.csv"
        path.write_text(path.read_text(encoding="utf-8").replace("840.0", "not-a-number"), encoding="utf-8")
    elif breakage == "missing_column":
        (root / "r1" / "origin_events.csv").write_text("route_id,vehicle_id\nr1,C\n", encoding="utf-8")
    else:
        (root / "r1" / "segments.csv").unlink()
        (root / "r1" / "origin_events.csv").unlink()
        (root / "r1" / "coverage.json").unlink()
        (root / "r1").rmdir()
    with pytest.raises(ValueError):
        snapshot_files.load_snapshot_dir(root)


def test_missing_folder_raises(tmp_path):
    with pytest.raises(ValueError):
        snapshot_files.load_snapshot_dir(tmp_path / "nowhere")


def _offline_client(monkeypatch, snapshot_dir):
    def no_database(*args, **kwargs):
        raise AssertionError("the database was touched in snapshot mode")

    monkeypatch.setattr(psycopg, "connect", no_database)
    monkeypatch.setattr(main, "_cache", None)  # restored afterwards; the lifespan sets it
    monkeypatch.setenv("SNAPSHOT_DIR", str(snapshot_dir))
    monkeypatch.setenv("DATABASE_URL", "postgresql://u:p@db.example.invalid:5432/x")  # must be ignored
    return TestClient(main.app)


def _curve_body(deadline):
    return {"route_id": MORNINGTON, "deadline": deadline, "walk_to_min": 5, "walk_from_min": 5, "tolerance": 0.1}


def test_demo_runs_with_no_database(monkeypatch):
    with _offline_client(monkeypatch, FROZEN) as client:
        advice = client.post("/api/departure-curve", json=_curve_body("2026-10-24T16:00:00Z")).json()
        assert advice["data_quality"]["status"] == "ok"
        assert advice["recommended"] is not None and advice["recommended"]["p_on_time"] >= 0.85
        assert "Offline snapshot frozen 24 Oct 16:55 UTC" in advice["data_quality"]["basis"]
        assert "±60 min" in advice["data_quality"]["basis"]

        none = client.post("/api/departure-curve", json=_curve_body("2026-10-24T14:30:00Z")).json()
        assert none["recommended"] is None

        routes = {r["route_id"]: r for r in client.get("/api/routes").json()}
        assert routes[MORNINGTON]["trips_observed"] == 26
        assert client.get("/api/calibration", params={"route_id": MORNINGTON}).status_code == 200
        assert client.get("/api/stats").json()["last_polled_at"].startswith("2026-10-24T16:55")


def test_a_bad_snapshot_dir_fails_startup_loudly(monkeypatch, tmp_path):
    monkeypatch.setattr(main, "_cache", None)
    monkeypatch.setenv("SNAPSHOT_DIR", str(tmp_path / "nowhere"))
    with pytest.raises(ValueError), TestClient(main.app):
        pass


def test_without_snapshot_dir_behaviour_is_unchanged(monkeypatch):
    monkeypatch.setattr(main, "_cache", None)
    monkeypatch.delenv("SNAPSHOT_DIR", raising=False)
    monkeypatch.setenv("DATABASE_URL", "")
    with TestClient(main.app) as client:
        body = client.post("/api/departure-curve", json=_curve_body("2026-10-24T16:00:00Z")).json()
        assert body["data_quality"]["status"] == "insufficient_data"  # "not connected", as before
