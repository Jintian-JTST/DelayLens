import json
from datetime import UTC, datetime

import numpy as np
import pytest
from fastapi.testclient import TestClient

from app import calibration, db, main, model
from app.main import app
from app.schemas import Stats

client = TestClient(app)
ROUTE = "test-tube"
START = datetime(2026, 10, 24, 12, 0, tzinfo=UTC)
END = datetime(2026, 10, 24, 18, 0, tzinfo=UTC)


def _segments(**kwargs):
    return model.synthetic_segments(START, END, headway_min=3, ride_min=11, **kwargs)


def test_training_view_never_sees_unfinished_runs():
    segs = _segments(ride_jitter_min=2, seed=1)
    t = int(segs.t_origin[40])
    train = calibration._training_view(segs, t)
    assert train is not None
    assert np.all(train.t_dest < t)
    assert train.coverage[0, 1] < t


def test_exact_timetable_is_well_calibrated():
    result = calibration.summarise(*calibration.backtest(_segments()))
    assert result.n_outcomes > 0
    assert result.brier_score is not None and result.brier_score < 0.05
    assert result.calibration_status == "preliminary"
    assert sum(b.n for b in result.bins) == result.n_outcomes
    assert "inferred" in result.basis


def test_noisy_timetable_gives_valid_scores():
    result = calibration.summarise(
        *calibration.backtest(_segments(headway_jitter_min=1, ride_jitter_min=2, seed=3))
    )
    assert 0 <= result.brier_score <= 1
    for b in result.bins:
        assert 0 <= b.predicted <= 1 and 0 <= b.observed <= 1 and b.n > 0


def test_too_few_runs_is_not_validated():
    short = model.synthetic_segments(START, START.replace(hour=12, minute=30), headway_min=10, ride_min=11)
    result = calibration.summarise(*calibration.backtest(short))
    assert result.calibration_status == "not_validated"
    assert result.bins == [] and result.brier_score is None


@pytest.fixture
def with_cache(monkeypatch, tmp_path):
    path = tmp_path / "routes.json"
    path.write_text(json.dumps([{
        "route_id": ROUTE, "line_id": "victoria", "direction": "outbound", "mode": "tube",
        "origin": {"naptan_id": "O", "name": "Origin"},
        "destination": {"naptan_id": "D", "name": "Destination"},
    }]), encoding="utf-8")
    monkeypatch.setattr(main, "ROUTES_PATH", path)
    syn = _segments(ride_jitter_min=1, seed=2)
    rows = [
        db.Segment(str(v), datetime.fromtimestamp(int(o), UTC), datetime.fromtimestamp(int(d), UTC),
                   float(d - o), datetime.fromtimestamp(int(o), UTC))
        for v, o, d in zip(syn.vehicle_id, syn.t_origin, syn.t_dest, strict=True)
    ]
    snapshot = db.Snapshot(
        segments={ROUTE: rows}, coverage={},
        stats=Stats(rows=0, chunks=0, compression_ratio=None, first_polled_at=None, last_polled_at=None),
        refreshed_at=START,
    )
    cache = db.SegmentCache("postgres://unused", loader=lambda url: snapshot)
    cache.refresh()
    monkeypatch.setattr(main, "_cache", cache)
    main._segments_memo.clear()
    main._calibration_memo.clear()


def test_endpoint_returns_backtest(with_cache):
    data = client.get("/api/calibration").json()
    assert data["calibration_status"] in {"preliminary", "not_validated"}
    assert data["n_outcomes"] > 0 and data["bins"]
    assert client.get("/api/calibration", params={"route_id": ROUTE}).status_code == 200


def test_endpoint_unknown_route_is_404(with_cache):
    assert client.get("/api/calibration", params={"route_id": "nope"}).status_code == 404


def test_endpoint_without_database_is_503(monkeypatch):
    monkeypatch.setattr(main, "_cache", None)
    assert client.get("/api/calibration").status_code == 503


def test_capture_gap_is_censored_not_scored_as_late():
    segs = _segments()
    keep = (segs.t_origin < segs.t_origin[0] + 3 * 3600) | (segs.t_origin > segs.t_origin[0] + 3 * 3600 + 20 * 60)
    gappy = model.Segments(
        segment_id=segs.segment_id[keep], vehicle_id=segs.vehicle_id[keep],
        t_origin=segs.t_origin[keep], t_dest=segs.t_dest[keep],
    )
    outcomes, censored = calibration.backtest(gappy)
    assert censored > 0
    result = calibration.summarise(outcomes, censored)
    assert result.brier_score < 0.05  # the 20-min hole did not count as late
    assert "suspected recording gaps" in result.basis
