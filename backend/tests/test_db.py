import json
from datetime import UTC, datetime

import psycopg
import pytest
from fastapi.testclient import TestClient

from app import db, main
from app.main import app
from app.schemas import Stats

client = TestClient(app)
ROUTE = "test-tube-outbound"
T0 = datetime(2026, 10, 24, 14, 0, tzinfo=UTC)


def _snapshot(trips=2):
    segments = [
        db.Segment(f"v{i}", T0, T0.replace(minute=11), 660.0, T0) for i in range(trips)
    ]
    return db.Snapshot(
        segments={ROUTE: segments},
        coverage={ROUTE: db.Coverage(trips, [T0])},
        origin_events={},
        poll_times=[],
        stats=Stats(rows=10335, chunks=2, compression_ratio=None,
                    first_polled_at=T0, last_polled_at=T0.replace(minute=30)),
        refreshed_at=T0,
    )


@pytest.fixture(autouse=True)
def isolate(monkeypatch, tmp_path):
    path = tmp_path / "routes.json"
    path.write_text(json.dumps([{
        "route_id": ROUTE, "line_id": "victoria", "direction": "outbound", "mode": "tube",
        "origin": {"naptan_id": "O", "name": "Origin"},
        "destination": {"naptan_id": "D", "name": "Destination"},
    }]), encoding="utf-8")
    monkeypatch.setattr(main, "ROUTES_PATH", path)
    monkeypatch.setattr(main, "_cache", None)


def _cache_with(snapshot):
    cache = db.SegmentCache("postgres://unused", loader=lambda url: snapshot)
    assert cache.refresh()
    return cache


def test_refresh_failure_keeps_last_good_snapshot():
    good = _snapshot()
    calls = iter([good])

    def loader(url):
        try:
            return next(calls)
        except StopIteration:
            raise psycopg.OperationalError("connection to host failed") from None

    cache = db.SegmentCache("postgres://unused", loader=loader)
    assert cache.refresh()
    assert not cache.refresh()
    assert cache.snapshot is good
    assert cache.last_error == "OperationalError"
    assert len(cache.segments(ROUTE)) == 2
    assert cache.segments("unknown") == []


def test_no_snapshot_before_first_load():
    cache = db.SegmentCache("postgres://unused", loader=lambda url: _snapshot())
    assert cache.snapshot is None
    assert cache.segments(ROUTE) == []


def test_routes_include_recorded_coverage(monkeypatch):
    monkeypatch.setattr(main, "_cache", _cache_with(_snapshot(trips=13)))
    route = client.get("/api/routes").json()[0]
    assert route["trips_observed"] == 13
    assert route["hours_covered"] == ["2026-10-24T14:00:00Z"]


def test_routes_without_database_show_zero():
    route = client.get("/api/routes").json()[0]
    assert route["trips_observed"] == 0
    assert route["hours_covered"] == []


def test_stats_from_snapshot(monkeypatch):
    monkeypatch.setattr(main, "_cache", _cache_with(_snapshot()))
    data = client.get("/api/stats").json()
    assert data["rows"] == 10335
    assert data["compression_ratio"] is None


def test_stats_without_database_is_503():
    assert client.get("/api/stats").status_code == 503


def test_curve_without_recorded_trips_gives_no_probability(monkeypatch):
    monkeypatch.setattr(main, "_cache", _cache_with(_snapshot(trips=3)))
    data = client.post("/api/departure-curve", json={
        "route_id": ROUTE, "deadline": "2026-10-25T11:00:00Z",
    }).json()
    assert data["points"] == []
    assert data["recommended"] is None
    assert data["data_quality"]["status"] == "insufficient_data"
    assert "3 trips recorded on this route" in data["data_quality"]["basis"]


def test_database_url_placeholder_is_ignored(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql://user:password@host:port/tsdb")
    assert main._database_url() == ""
