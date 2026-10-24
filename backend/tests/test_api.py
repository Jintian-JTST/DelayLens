from datetime import UTC, datetime

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)
ROUTE_ID = "fixture-bus-outbound"


def _curve_body(**overrides):
    body = {
        "route_id": ROUTE_ID,
        "deadline": datetime(2026, 10, 25, 11, 0, tzinfo=UTC).isoformat(),
        "walk_to_min": 6,
        "walk_from_min": 4,
        "tolerance": 0.10,
        "window_min": 90,
    }
    body.update(overrides)
    return body


def test_health():
    assert client.get("/api/health").json() == {"status": "ok"}


def test_routes_lists_fixture_route():
    data = client.get("/api/routes").json()
    assert data[0]["route_id"] == ROUTE_ID


def test_curve_shape_and_monotonic():
    r = client.post("/api/departure-curve", json=_curve_body())
    assert r.status_code == 200
    data = r.json()
    assert len(data["points"]) == 91
    ps = [p["p_on_time"] for p in data["points"]]
    assert ps == sorted(ps, reverse=True)
    assert data["recommended"] is not None
    assert "FIXTURE" in data["data_quality"]["basis"]
    assert [w["delay_min"] for w in data["what_if"]] == [5, 10, 15]


def test_unknown_route_is_404():
    r = client.post("/api/departure-curve", json=_curve_body(route_id="nope"))
    assert r.status_code == 404


def test_invalid_tolerance_is_422():
    r = client.post("/api/departure-curve", json=_curve_body(tolerance=1.5))
    assert r.status_code == 422


def test_ask_is_honest_when_unavailable():
    r = client.post("/api/ask", json={"question": "when should I leave?"})
    assert r.json()["status"] == "gemini_unavailable"


def test_live_never_fakes_data():
    assert client.get("/api/live", params={"route_id": ROUTE_ID}).status_code == 503
