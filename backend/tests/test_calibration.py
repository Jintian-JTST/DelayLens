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


def test_held_out_block_is_disjoint_from_training():
    segs = _segments(ride_jitter_min=2, seed=1)
    a = int(segs.t_origin[0]) + 3600
    b = a + 1800
    train = calibration._held_out_training(segs, a, b)
    assert train is not None
    assert not np.any((train.t_origin >= a) & (train.t_origin < b))
    assert not np.any((train.coverage[:, 0] < b) & (train.coverage[:, 1] >= a))


def test_bus_timetable_gets_outcomes():
    # M's case: 8-min headway, 18-min ride. A forward-only window had 0 outcomes.
    bus = model.synthetic_segments(START, END, headway_min=8, ride_min=18)
    outcomes, _ = calibration.backtest(bus)
    result = calibration.summarise(outcomes)
    assert result.n_outcomes > 0
    # Not ~0: the real outcome depends on the exact phase against an 8-min
    # timetable, while the model averages over +/-30 min of phases.
    assert result.brier_score < 0.15
    assert result.calibration_status == "preliminary"


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
        segments={ROUTE: rows}, coverage={}, origin_events={}, poll_times=[],
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


def test_recording_gap_is_set_aside_not_scored_as_late():
    segs = _segments()
    t0 = int(segs.t_origin[0])
    hole = (segs.t_origin >= t0 + 3 * 3600) & (segs.t_origin < t0 + 3 * 3600 + 20 * 60)
    end_t = int(segs.coverage[0, 1])
    gappy = model.Segments(
        segment_id=segs.segment_id[~hole], vehicle_id=segs.vehicle_id[~hole],
        t_origin=segs.t_origin[~hole], t_dest=segs.t_dest[~hole],
        coverage=np.array([[t0, t0 + 3 * 3600 - 1], [t0 + 3 * 3600 + 20 * 60, end_t]]),
    )
    outcomes, set_aside = calibration.backtest(gappy)
    assert set_aside > 0
    result = calibration.summarise(outcomes, set_aside)
    assert result.brier_score < 0.05  # the hole did not count as late
    assert "set aside" in result.basis


def test_unconfirmed_bus_makes_outcome_unknown():
    segs = _segments()
    # Pretend run 60 was seen leaving but never matched at the destination.
    drop = np.arange(len(segs)) == 60
    partial = model.Segments(
        segment_id=segs.segment_id[~drop], vehicle_id=segs.vehicle_id[~drop],
        t_origin=segs.t_origin[~drop], t_dest=segs.t_dest[~drop],
        coverage=segs.coverage, unconfirmed_departures=segs.t_origin[drop],
    )
    board = int(segs.t_origin[60]) - 30
    assert calibration._known_outcome(partial, board, board + 3600) is None
    assert calibration._known_outcome(segs, board, board + 3600) == 60
