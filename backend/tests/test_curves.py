"""Model wiring: D's segments -> M's model -> the API contract."""

import json
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from app import curves, db, main, model
from app.main import app
from app.schemas import Stats

client = TestClient(app)
ROUTE = "test-bus"
START = datetime(2026, 10, 24, 12, 0, tzinfo=UTC)
END = datetime(2026, 10, 24, 20, 0, tzinfo=UTC)


def _rows_from_synthetic(**kwargs):
    syn = model.synthetic_segments(START, END, **kwargs)
    return [
        db.Segment(
            vehicle_id=str(v),
            origin_observed_at=datetime.fromtimestamp(int(o), UTC),
            destination_observed_at=datetime.fromtimestamp(int(d), UTC),
            ride_seconds=float(d - o),
            origin_episode_started_at=datetime.fromtimestamp(int(o), UTC),
        )
        for v, o, d in zip(syn.vehicle_id, syn.t_origin, syn.t_dest, strict=True)
    ]


@pytest.fixture(autouse=True)
def isolate(monkeypatch, tmp_path, request):
    path = tmp_path / "routes.json"
    path.write_text(json.dumps([{
        "route_id": ROUTE, "line_id": "29", "direction": "outbound", "mode": "bus",
        "origin": {"naptan_id": "O", "name": "Origin"},
        "destination": {"naptan_id": "D", "name": "Destination"},
    }]), encoding="utf-8")
    monkeypatch.setattr(main, "ROUTES_PATH", path)
    headway = getattr(request, "param", 3)
    rows = _rows_from_synthetic(headway_min=headway, ride_min=20)
    snapshot = db.Snapshot(
        segments={ROUTE: rows},
        coverage={ROUTE: db.Coverage(len(rows), [])},
        origin_events={},
        poll_times=[],
        stats=Stats(rows=0, chunks=0, compression_ratio=None,
                    first_polled_at=None, last_polled_at=None),
        refreshed_at=START,
    )
    cache = db.SegmentCache("postgres://unused", loader=lambda url: snapshot)
    cache.refresh()
    monkeypatch.setattr(main, "_cache", cache)
    main._segments_memo.clear()


def _curve(**overrides):
    body = {"route_id": ROUTE, "deadline": "2026-10-24T17:00:00Z",
            "walk_to_min": 0, "walk_from_min": 0, "tolerance": 0.10}
    body.update(overrides)
    return client.post("/api/departure-curve", json=body).json()


def test_real_model_curve_on_hand_checkable_timetable():
    # A run every 3 min, 20-min ride, 1-min boarding buffer: leaving by 16:20
    # always makes 17:00; at 16:50 nothing can.
    data = _curve()
    assert data["data_quality"]["status"] == "ok"
    ps = [p["p_on_time"] for p in data["points"]]
    assert ps == sorted(ps, reverse=True)
    by_time = {p["depart_at"]: p["p_on_time"] for p in data["points"]}
    assert by_time["2026-10-24T16:20:00Z"] == 1.0
    assert by_time["2026-10-24T16:50:00Z"] == 0.0
    assert data["recommended"] is not None
    assert data["recommended"]["p_on_time"] >= 0.9
    assert "trips recorded on this route" in data["data_quality"]["basis"]
    for p in data["points"]:
        lo, hi = p["ci"]
        assert lo <= p["p_on_time"] <= hi


def test_basis_discloses_the_time_of_day_window():
    # PLAN section 4 allows a +/-60 min window only if it is disclosed.
    basis = _curve()["data_quality"]["basis"]
    assert "±60 min" in basis
    assert f"±{curves.TOD_WINDOW_MIN} min" in basis


def test_what_if_is_relative_to_recommendation():
    data = _curve()
    rec = data["recommended"]["p_on_time"]
    for w in data["what_if"]:
        assert w["p_on_time"] <= rec
        assert w["delta"] == pytest.approx(w["p_on_time"] - rec, abs=1e-4)


def test_deadline_on_unrecorded_date_is_insufficient():
    data = _curve(deadline="2026-10-26T17:00:00Z")
    assert data["data_quality"]["status"] == "insufficient_data"
    assert data["points"] == []
    assert data["recommended"] is None


def test_duplicate_runs_are_counted_once():
    t = START
    row = db.Segment("v1", t, t + timedelta(minutes=20), 1200.0, t)
    segments = curves.to_segments([row, row])
    assert len(segments) == 1


def test_wilson_band_is_valid():
    assert curves._wilson(1.0, 20)[1] == 1.0
    lo, hi = curves._wilson(0.5, 20)
    assert 0 < lo < 0.5 < hi < 1
    assert curves._wilson(0.5, 0) == (0.0, 1.0)


@pytest.mark.parametrize("isolate", [10], indirect=True)
def test_ten_minute_headway_never_reaches_ok_on_one_date():
    # Known limit (tasks/model.md): replay uses only the deadline's date +/- 30 min,
    # so a 10-min service shows ~7 runs: low_data, probabilities but no advice.
    data = _curve()
    assert data["data_quality"]["status"] == "low_data"
    assert data["points"]
    assert data["recommended"] is None


def test_ok_rows_use_the_model_bootstrap_band(monkeypatch):
    seen = {}
    real = model.departure_curve

    def spy(*args, **kwargs):
        seen["curve"] = real(*args, **kwargs)
        return seen["curve"]

    monkeypatch.setattr(model, "departure_curve", spy)
    data = _curve()
    curve = seen["curve"]
    ok_rows = [i for i, s in enumerate(curve.status) if s == "ok"]
    assert ok_rows
    by_time = {p["depart_at"]: p for p in data["points"]}
    for i in ok_rows:
        point = by_time[curves._utc(curve.depart_at[i]).isoformat().replace("+00:00", "Z")]
        assert point["ci"] == [round(float(curve.ci_low[i]), 4), round(float(curve.ci_high[i]), 4)]


def test_recommendation_matches_model_advisor(monkeypatch):
    data = _curve()
    advice = model.recommend(
        model.departure_curve(
            curves.to_segments(main._cache.segments(ROUTE)),
            datetime(2026, 10, 24, 17, 0, tzinfo=UTC),
        ),
        0.10,
    )
    assert advice.reason == "ok"
    expected = curves._utc(advice.depart_at).isoformat().replace("+00:00", "Z")
    assert data["recommended"]["depart_at"] == expected


def test_poll_gaps_split_coverage_and_unmatched_departures_are_unconfirmed():
    polls = [START + timedelta(seconds=30 * k) for k in range(20)]
    polls += [polls[-1] + timedelta(minutes=10) + timedelta(seconds=30 * k) for k in range(20)]
    cov = curves.poll_coverage(polls)
    assert len(cov) == 2
    t = START + timedelta(minutes=1)
    used = db.Segment("v1", t, t + timedelta(minutes=20), 1200.0, t)
    unmatched = db.OriginEvent("v2", t + timedelta(minutes=2), t + timedelta(minutes=2))
    segments = curves.to_segments(
        [used], [db.OriginEvent("v1", t, t), unmatched], polls
    )
    assert list(segments.unconfirmed_departures) == [model.to_epoch(unmatched.observed_at)]
    assert segments.coverage.shape == (2, 2)
