import json
from datetime import UTC, datetime
from functools import partial

import httpx
import pytest
from fastapi.testclient import TestClient

from app import ask, main
from app.main import app

client = TestClient(app)
ROUTE = "fixture-bus-outbound"
SECRET = "gemini-secret-never-returned"


@pytest.fixture(autouse=True)
def isolate(monkeypatch, tmp_path):
    monkeypatch.setattr(main, "ROUTES_PATH", tmp_path / "routes.json")
    monkeypatch.setenv("GEMINI_API_KEY", SECRET)
    monkeypatch.delenv("TFL_APP_KEY", raising=False)
    monkeypatch.delenv("ASK_ACCESS_CODE", raising=False)


def _gemini(monkeypatch, handler):
    monkeypatch.setattr(
        ask,
        "answer_question",
        partial(ask.answer_question, transport=httpx.MockTransport(handler)),
    )


def _call(name, args=None):
    def handler(request):
        assert request.headers["x-goog-api-key"] == SECRET
        body = json.loads(request.content)
        assert body["toolConfig"]["functionCallingConfig"]["mode"] == "ANY"
        return httpx.Response(
            200,
            json={"candidates": [{"content": {"parts": [{"functionCall": {"name": name, "args": args or {}}}]}}]},
        )

    return handler


def _ask(question="when should I leave?"):
    return client.post("/api/ask", json={"question": question})


def test_departure_curve_answer_is_templated_from_our_numbers(monkeypatch):
    _gemini(monkeypatch, _call("get_departure_curve", {
        "route_id": ROUTE, "deadline": "2026-10-25T11:00:00+00:00", "tolerance": 0.05,
    }))
    data = _ask().json()
    assert data["status"] == "ok"
    assert data["interpretation"]["tolerance"] == 0.05
    assert data["curve"]["recommended"] is not None
    rec = data["curve"]["recommended"]
    assert f"{round(rec['p_on_time'] * 100)}%" in data["answer"]
    assert SECRET not in json.dumps(data)


def test_compare_departures_names_the_better_option(monkeypatch):
    _gemini(monkeypatch, _call("compare_departures", {
        "route_id": ROUTE,
        "deadline": "2026-10-25T11:00:00+00:00",
        "departures": ["2026-10-25T10:00:00+00:00", "2026-10-25T10:20:00+00:00"],
    }))
    data = _ask("10:00 or 10:20?").json()
    assert data["status"] == "ok"
    assert "Best: 10:00" in data["answer"]
    assert len(data["interpretation"]["compare"]) == 2


def test_compare_outside_window_is_reported(monkeypatch):
    _gemini(monkeypatch, _call("compare_departures", {
        "route_id": ROUTE,
        "deadline": "2026-10-25T11:00:00+00:00",
        "departures": ["2026-10-24T01:00:00+00:00", "2026-10-25T10:20:00+00:00"],
    }))
    assert "outside" in _ask().json()["answer"]


def test_unknown_route_is_unsupported(monkeypatch):
    _gemini(monkeypatch, _call("get_departure_curve", {
        "route_id": "made-up", "deadline": "2026-10-25T11:00:00+00:00",
    }))
    assert _ask().json()["status"] == "unsupported_route"


def test_list_routes(monkeypatch):
    _gemini(monkeypatch, _call("list_routes"))
    data = _ask("what can you do?").json()
    assert data["status"] == "ok"
    assert "Fixture Origin" in data["answer"]


def test_off_topic_is_unclear(monkeypatch):
    _gemini(monkeypatch, _call("unclear"))
    assert _ask("what's the capital of France").json()["status"] == "unclear"


@pytest.mark.parametrize("args", [
    {"route_id": ROUTE, "deadline": "tomorrow"},
    {"route_id": ROUTE},
    {"route_id": ROUTE, "deadline": "2026-10-25T11:00:00+00:00", "tolerance": 7},
])
def test_invalid_arguments_are_unclear_not_guessed(monkeypatch, args):
    _gemini(monkeypatch, _call("get_departure_curve", args))
    assert _ask().json()["status"] == "unclear"


def test_live_failure_is_explicit(monkeypatch):
    _gemini(monkeypatch, _call("get_live", {"route_id": ROUTE}))
    data = _ask("next bus?").json()
    assert data["status"] == "unclear"
    assert "unavailable" in data["answer"]


@pytest.mark.parametrize("response", [
    httpx.Response(500),
    httpx.Response(429),
    httpx.Response(200, text="not json"),
    httpx.Response(200, json={"candidates": []}),
    httpx.Response(200, json={"candidates": [{"content": {"parts": [{"text": "hi"}]}}]}),
])
def test_gemini_failures_fall_back(monkeypatch, response):
    _gemini(monkeypatch, lambda request: response)
    data = _ask().json()
    assert data["status"] == "gemini_unavailable"
    assert SECRET not in json.dumps(data)


def test_gemini_timeout_falls_back(monkeypatch):
    def handler(request):
        raise httpx.ReadTimeout(str(request.url), request=request)

    _gemini(monkeypatch, handler)
    assert _ask().json()["status"] == "gemini_unavailable"


def test_missing_key_never_calls_gemini(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY")

    def unexpected(request):
        pytest.fail("Gemini must not be called without a key")

    _gemini(monkeypatch, unexpected)
    assert _ask().json()["status"] == "gemini_unavailable"


def test_empty_question_is_422():
    assert client.post("/api/ask", json={"question": ""}).status_code == 422


def test_model_supplied_offset_is_ignored_for_london_wall_clock(monkeypatch):
    # Clocks go back at 02:00 on 25 Oct, so 14:00 that day is +00:00, not +01:00.
    _gemini(monkeypatch, _call("get_departure_curve", {
        "route_id": ROUTE, "deadline": "2026-10-25T14:00:00+01:00",
    }))
    data = _ask().json()
    assert data["interpretation"]["deadline"] == "2026-10-25T14:00:00Z"
    assert "arriving by 14:00" in data["answer"]


def test_local_time_without_offset_is_accepted(monkeypatch):
    _gemini(monkeypatch, _call("get_departure_curve", {
        "route_id": ROUTE, "deadline": "2026-10-24T14:00:00",
    }))
    data = _ask().json()
    deadline = datetime.fromisoformat(data["interpretation"]["deadline"])
    assert deadline == datetime(2026, 10, 24, 13, 0, tzinfo=UTC)  # BST is UTC+1
    assert "arriving by 14:00" in data["answer"]
