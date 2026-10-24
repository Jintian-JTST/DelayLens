import json
from datetime import UTC, datetime
from functools import partial

import httpx
import pytest
from app import main, tfl
from app.main import app
from fastapi.testclient import TestClient

client = TestClient(app)
ROUTE_ID = "fixture-bus-outbound"


@pytest.fixture(autouse=True)
def isolate_config(monkeypatch, tmp_path):
    monkeypatch.setattr(main, "ROUTES_PATH", tmp_path / "routes.json")
    monkeypatch.delenv("TFL_APP_KEY", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)


@pytest.fixture
def configured_route():
    route = {
        "route_id": "test-bus-outbound",
        "line_id": "24",
        "direction": "outbound",
        "mode": "bus",
        "origin": {"naptan_id": "TEST-O", "name": "Test origin"},
        "destination": {"naptan_id": "TEST-D", "name": "Test destination"},
    }
    main.ROUTES_PATH.write_text(json.dumps([route]), encoding="utf-8")
    return route


def _prediction(**overrides):
    prediction = {
        "vehicleId": "bus-1",
        "lineId": "24",
        "naptanId": "TEST-O",
        "direction": "outbound",
        "destinationName": "Test terminus",
        "timeToStation": 120,
        "expectedArrival": "2026-10-24T15:02:00+01:00",
    }
    prediction.update(overrides)
    return prediction


def _mock_tfl(monkeypatch, handler):
    monkeypatch.setenv("TFL_APP_KEY", "test-key-never-returned")
    monkeypatch.setattr(
        tfl, "get_live", partial(tfl.get_live, transport=httpx.MockTransport(handler))
    )


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
    response = client.get("/api/live", params={"route_id": ROUTE_ID})
    assert response.status_code == 503
    assert response.json() == {"error": "tfl_unavailable"}


def test_routes_load_data_team_config(configured_route):
    response = client.get("/api/routes")
    assert response.status_code == 200
    route = response.json()[0]
    assert route["route_id"] == configured_route["route_id"]
    assert route["trips_observed"] == 0
    assert route["hours_covered"] == []
    assert "direction" not in route  # Keep the public contract unchanged.


@pytest.mark.parametrize("raw", ["{", "{}", "[{}]"])
def test_invalid_config_does_not_silently_load_fixtures(raw):
    main.ROUTES_PATH.write_text(raw, encoding="utf-8")
    response = client.get("/api/routes")
    assert response.status_code == 503
    assert response.json() == {"detail": "route_config_unavailable"}


def test_duplicate_route_ids_are_rejected(configured_route):
    main.ROUTES_PATH.write_text(json.dumps([configured_route] * 2), encoding="utf-8")
    assert client.get("/api/routes").status_code == 503


def test_real_routes_never_get_fixture_probabilities(configured_route):
    response = client.post(
        "/api/departure-curve", json=_curve_body(route_id=configured_route["route_id"])
    )
    assert response.status_code == 200
    data = response.json()
    assert data["points"] == []
    assert data["recommended"] is None
    assert data["what_if"] == []
    assert data["data_quality"]["status"] == "insufficient_data"


def test_live_filters_sorts_and_normalizes_to_utc(monkeypatch, configured_route):
    def handler(request):
        assert request.url.host == "api.tfl.gov.uk"
        assert request.url.path == "/Line/24/Arrivals/TEST-O"
        assert request.url.params["direction"] == "outbound"
        assert request.url.params["app_key"] == "test-key-never-returned"
        assert request.extensions["timeout"]["read"] == 3.0
        return httpx.Response(
            200,
            json=[
                _prediction(),
                _prediction(
                    vehicleId="earlier",
                    timeToStation=60,
                    expectedArrival="2026-10-24T14:01:00Z",
                ),
                _prediction(naptanId="OTHER"),
                _prediction(lineId="different"),
                _prediction(direction="inbound"),
            ],
        )

    _mock_tfl(monkeypatch, handler)
    response = client.get(
        "/api/live", params={"route_id": configured_route["route_id"]}
    )
    assert response.status_code == 200
    data = response.json()
    assert [a["vehicle_id"] for a in data["arrivals"]] == ["earlier", "bus-1"]
    assert data["arrivals"][1]["expected_arrival"] == "2026-10-24T14:02:00Z"
    assert datetime.fromisoformat(data["fetched_at"]).utcoffset().total_seconds() == 0
    assert "test-key" not in response.text


def test_empty_tfl_result_is_valid(monkeypatch, configured_route):
    _mock_tfl(monkeypatch, lambda request: httpx.Response(200, json=[]))
    response = client.get(
        "/api/live", params={"route_id": configured_route["route_id"]}
    )
    assert response.status_code == 200
    assert response.json()["arrivals"] == []


@pytest.mark.parametrize("status", [401, 403, 429, 500, 503])
def test_tfl_http_errors_are_explicit(monkeypatch, configured_route, status):
    _mock_tfl(monkeypatch, lambda request: httpx.Response(status))
    response = client.get(
        "/api/live", params={"route_id": configured_route["route_id"]}
    )
    assert response.status_code == 503
    assert response.json() == {"error": "tfl_unavailable"}


@pytest.mark.parametrize("error", [httpx.ReadTimeout, httpx.ConnectError])
def test_tfl_network_errors_do_not_leak_keys(monkeypatch, configured_route, error):
    def handler(request):
        raise error(str(request.url), request=request)

    _mock_tfl(monkeypatch, handler)
    response = client.get(
        "/api/live", params={"route_id": configured_route["route_id"]}
    )
    assert response.status_code == 503
    assert response.json() == {"error": "tfl_unavailable"}


@pytest.mark.parametrize(
    "payload",
    [
        {},
        [None],
        [_prediction(timeToStation=-1)],
        [_prediction(expectedArrival="invalid")],
        [_prediction(expectedArrival="2026-10-24T14:02:00")],
        [_prediction(vehicleId="")],
        [_prediction(lineId=None)],
        [_prediction(naptanId=None)],
    ],
)
def test_bad_tfl_payload_is_unavailable(monkeypatch, configured_route, payload):
    _mock_tfl(monkeypatch, lambda request: httpx.Response(200, json=payload))
    response = client.get(
        "/api/live", params={"route_id": configured_route["route_id"]}
    )
    assert response.status_code == 503
    assert response.json() == {"error": "tfl_unavailable"}


def test_tfl_non_json_is_unavailable(monkeypatch, configured_route):
    _mock_tfl(monkeypatch, lambda request: httpx.Response(200, text="not JSON"))
    response = client.get(
        "/api/live", params={"route_id": configured_route["route_id"]}
    )
    assert response.status_code == 503


def test_missing_key_never_calls_tfl(monkeypatch, configured_route):
    def unexpected_request(request):
        pytest.fail("TfL must not be called without a configured key")

    _mock_tfl(monkeypatch, unexpected_request)
    monkeypatch.delenv("TFL_APP_KEY")
    response = client.get(
        "/api/live", params={"route_id": configured_route["route_id"]}
    )
    assert response.status_code == 503


def test_unknown_live_route_is_404():
    assert client.get("/api/live", params={"route_id": "unknown"}).status_code == 404


def test_tube_without_direction_does_not_mix_platforms(monkeypatch, configured_route):
    configured_route["mode"] = "tube"
    configured_route.pop("direction")
    main.ROUTES_PATH.write_text(json.dumps([configured_route]), encoding="utf-8")

    def unexpected_request(request):
        pytest.fail("Tube live arrivals need a configured direction")

    _mock_tfl(monkeypatch, unexpected_request)
    response = client.get(
        "/api/live", params={"route_id": configured_route["route_id"]}
    )
    assert response.status_code == 503
