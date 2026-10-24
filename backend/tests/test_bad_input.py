"""Bad-input regression (T25/T31): hostile requests must never produce a 500.

Run in fixture mode. Deadlines at year 1 or 9999 overflow only the dev fixture generator
(app/fixtures.py); on the snapshot and database paths they returned 200 in T25, so they are
not asserted here.
"""

import json

import pytest
from fastapi.testclient import TestClient

from app import main
from app.main import app

client = TestClient(app)
ROUTE_ID = "fixture-bus-outbound"
OK = {
    "route_id": ROUTE_ID,
    "deadline": "2026-10-24T16:00:00Z",
    "walk_to_min": 5,
    "walk_from_min": 5,
    "tolerance": 0.1,
}
JSON_HEADERS = {"content-type": "application/json"}


@pytest.fixture(autouse=True)
def isolate_config(monkeypatch, tmp_path):
    monkeypatch.setattr(main, "ROUTES_PATH", tmp_path / "routes.json")
    for name in ("TFL_APP_KEY", "GEMINI_API_KEY", "ASK_ACCESS_CODE"):
        monkeypatch.delenv(name, raising=False)


def _without(key):
    return {k: v for k, v in OK.items() if k != key}


# name -> (body, expected status). The model never runs for a rejected body.
CURVE_CASES = {
    "missing deadline": (_without("deadline"), 422),
    "empty object": ({}, 422),
    "deadline text": ({**OK, "deadline": "not-a-date"}, 422),
    "deadline naive": ({**OK, "deadline": "2026-10-24T16:00:00"}, 422),
    "deadline null": ({**OK, "deadline": None}, 422),
    "route unknown": ({**OK, "route_id": "nope"}, 404),
    "route int": ({**OK, "route_id": 5}, 422),
    "route null": ({**OK, "route_id": None}, 422),
    "route huge": ({**OK, "route_id": "x" * 100_000}, 404),
    "walk negative": ({**OK, "walk_to_min": -5}, 422),
    "walk huge": ({**OK, "walk_to_min": 10**9}, 422),
    "walk text": ({**OK, "walk_to_min": "abc"}, 422),
    "tolerance zero": ({**OK, "tolerance": 0}, 422),
    "tolerance one": ({**OK, "tolerance": 1}, 422),
    "tolerance negative": ({**OK, "tolerance": -1}, 422),
    "tolerance text": ({**OK, "tolerance": "x"}, 422),
    "window huge": ({**OK, "window_min": 10**6}, 422),
}


@pytest.mark.parametrize("name", CURVE_CASES)
def test_curve_bad_json_body(name):
    body, expected = CURVE_CASES[name]
    r = client.post("/api/departure-curve", json=body)
    assert r.status_code == expected


def test_curve_deadline_int_is_read_as_epoch():
    r = client.post("/api/departure-curve", json={**OK, "deadline": 12345})
    assert r.status_code == 200


@pytest.mark.parametrize("walk", ["1e400", "-1e400", "NaN"])
def test_curve_non_finite_number_is_422(walk):
    body = json.dumps(OK).replace('"walk_to_min": 5', f'"walk_to_min": {walk}')
    r = client.post("/api/departure-curve", content=body, headers=JSON_HEADERS)
    assert r.status_code == 422
    assert all("input" not in e for e in r.json()["detail"])


RAW_CASES = {
    "invalid json": (b"{not json", JSON_HEADERS),
    "empty body": (b"", JSON_HEADERS),
    "wrong content type": (b"deadline=1", {"content-type": "text/plain"}),
    "array": (b"[1,2]", JSON_HEADERS),
    "deeply nested": (b"[" * 5000 + b"]" * 5000, JSON_HEADERS),
}


@pytest.mark.parametrize("path", ["/api/departure-curve", "/api/ask"])
@pytest.mark.parametrize("name", RAW_CASES)
def test_raw_body_is_client_error(path, name):
    content, headers = RAW_CASES[name]
    r = client.post(path, content=content, headers=headers)
    assert 400 <= r.status_code < 500  # 400 on Python 3.11, 422 on 3.14


@pytest.mark.parametrize(
    "body",
    [
        {},
        {"question": ""},
        {"question": 5},
        {"question": None},
        {"q": "hi"},
        {"question": "a" * 300_000},
        {"question": "ok", "extra": "x"},
    ],
    ids=["empty", "blank", "int", "null", "wrong key", "300k chars", "extra key"],
)
def test_ask_bad_body_never_5xx(body):
    r = client.post("/api/ask", json=body)
    assert r.status_code < 500
    if "question" not in body or body["question"] in ("", 5, None) or len(str(body["question"])) > 500:
        assert r.status_code == 422


@pytest.mark.parametrize(
    "path",
    [
        "/api/calibration",
        "/api/calibration?route_id=nope",
        "/api/calibration?route_id=" + "x" * 50_000,
        "/api/live?route_id=nope",
        "/api/nonexistent",
    ],
)
def test_get_bad_query_is_never_500(path):
    # 503 is the honest answer when no recorded data is connected.
    assert client.get(path).status_code in (200, 404, 422, 503)
