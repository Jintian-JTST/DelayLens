"""Regression checks for routes and the two preserved recorder entry points."""

import json

from fastapi.testclient import TestClient

from app.main import app
from ingest import database_poller, poller
from ingest.common import load_route
from ingest.settings import Settings, load_routes


def test_integrated_defaults_cover_short_and_legacy_routes(monkeypatch):
    for name in ("POLL_LINE_IDS", "POLL_STOP_IDS", "POLL_INTERVAL_SECONDS", "RAW_BACKUP_DIR"):
        monkeypatch.delenv(name, raising=False)
    settings = Settings.read()
    short = load_route()
    assert short["line_id"] == "24"
    assert 4 <= len(short["stops"]) <= 8
    for route in load_routes():
        assert route["line_id"] in settings.line_ids
        assert {route["origin"]["naptan_id"], route["destination"]["naptan_id"]} <= settings.stop_ids
    bus29 = next(route for route in load_routes() if route["line_id"] == "29")
    assert bus29["origin"]["naptan_id"] == "490015078M"


def test_raw_recorder_keeps_complete_response_without_database(tmp_path, monkeypatch):
    route = load_route()
    stops = [{"id": stop["naptan_id"]} for stop in route["stops"]]
    predictions = [{"lineId": "24", "naptanId": "outside-selected-stops"}]

    def fetch(path, key):
        if "/Route/Sequence/" in path:
            payload = {"stopPointSequences": [{"stopPoint": stops}]}
        elif path.endswith("/Status"):
            payload = [{"lineStatuses": [{"statusSeverityDescription": "Good Service"}]}]
        else:
            payload = predictions
        return {"http_status": 200, "error": None, "payload": payload,
                "received_at": "2026-10-24T14:00:00Z"}

    monkeypatch.setattr(poller, "fetch_json", fetch)
    monkeypatch.setattr(poller, "process_run", lambda *args, **kwargs: None)
    monkeypatch.delenv("DATABASE_URL", raising=False)
    run = tmp_path / "raw-run"
    assert poller.record(run, minutes=0.001) == 0
    saved = [json.loads(line) for line in (run / "polls.jsonl").read_text().splitlines()]
    assert saved[0]["payload"] == predictions
    assert saved[0]["poll_id"] and saved[0]["collector_id"]
    assert (run / "polls.jsonl.gz").exists()
    assert json.loads((run / "run.json").read_text())["status"] == "completed"
    assert callable(database_poller.flush_pending)


def test_actual_route_config_serves_no_synthetic_probabilities(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    with TestClient(app) as client:
        response = client.get("/api/routes")
        assert response.status_code == 200
        assert {r["route_id"] for r in response.json()} == {r["route_id"] for r in load_routes()}
        for route in response.json():
            result = client.post("/api/departure-curve", json={
                "route_id": route["route_id"], "deadline": "2026-10-24T18:00:00Z",
            })
            assert result.status_code == 200
            data = result.json()
            assert data["data_quality"]["status"] == "insufficient_data"
            assert data["points"] == []
            assert data["recommended"] is None
