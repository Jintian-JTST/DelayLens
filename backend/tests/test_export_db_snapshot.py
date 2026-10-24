import csv
import json
from datetime import UTC, datetime, timedelta

from app import db, model
from app.schemas import Stats
from tools import export_db_snapshot

T0 = datetime(2026, 10, 24, 14, 0, tzinfo=UTC)
ROUTE = "bus-29-test"


def _snapshot() -> db.Snapshot:
    return db.Snapshot(
        segments={
            ROUTE: [
                db.Segment("v2", T0 + timedelta(minutes=10), T0 + timedelta(minutes=22), 720.0,
                           T0 + timedelta(minutes=9)),
                db.Segment("v1", T0, T0 + timedelta(minutes=11), 660.0, T0),
            ],
            "other-route": [db.Segment("v9", T0, T0 + timedelta(minutes=5), 300.0, T0)],
        },
        coverage={ROUTE: db.Coverage(2, [T0])},
        origin_events={ROUTE: [db.OriginEvent("v3", T0, T0 + timedelta(minutes=5))]},
        poll_times=[T0 + timedelta(seconds=30), T0],
        stats=Stats(rows=1, chunks=1, compression_ratio=None,
                    first_polled_at=T0, last_polled_at=T0),
        refreshed_at=T0 + timedelta(hours=1),
    )


def test_export_writes_filtered_routes_in_time_order(tmp_path):
    summary = export_db_snapshot.export(_snapshot(), tmp_path, "bus-29")

    assert list(summary["routes"]) == [ROUTE]
    assert not (tmp_path / "other-route").exists()
    with open(tmp_path / ROUTE / "segments.csv", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    assert [r["vehicle_id"] for r in rows] == ["v1", "v2"]
    assert summary["routes"][ROUTE]["segments"] == 2
    assert summary["poll_count"] == 2
    assert summary["first_poll_utc"] == T0.isoformat()
    cov = json.loads((tmp_path / ROUTE / "coverage.json").read_text(encoding="utf-8"))
    assert cov == {"trips_observed": 2, "hours_covered": [T0.isoformat()]}


def test_exported_rows_round_trip_to_the_same_timestamps(tmp_path):
    export_db_snapshot.export(_snapshot(), tmp_path, ROUTE)
    with open(tmp_path / ROUTE / "segments.csv", encoding="utf-8") as f:
        first = next(csv.DictReader(f))
    assert model.to_epoch(datetime.fromisoformat(first["origin_observed_at"])) == model.to_epoch(T0)
    with open(tmp_path / ROUTE / "origin_events.csv", encoding="utf-8") as f:
        assert next(csv.DictReader(f))["vehicle_id"] == "v3"


def test_main_refuses_placeholder_database_url(monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(export_db_snapshot, "load_dotenv", lambda: None)
    monkeypatch.setenv("DATABASE_URL", "postgres://user:password@host/db")
    assert export_db_snapshot.main(["--out", str(tmp_path)]) == 2
    assert "not configured" in capsys.readouterr().err
