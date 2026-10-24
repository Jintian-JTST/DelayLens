"""Ask answers name the route, the assumed walks and the window, and flag past deadlines.

Gemini is mocked and `now` is fixed, so these cannot regress with the clock or the model.
"""

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import httpx

from app import ask
from app.schemas import (
    CurvePoint,
    DataQuality,
    DepartureCurveRequest,
    DepartureCurveResponse,
    LiveResponse,
    Recommended,
    Route,
)

BACKEND = Path(__file__).resolve().parent.parent
BUS29 = "bus-29-outbound-mornington-crescent-tottenham-court-road"
SUNDAY_MORNING = datetime(2026, 10, 25, 10, 0, tzinfo=UTC)  # Sun 25 Oct, 10:00 London


def _routes() -> list[Route]:
    raw = json.loads((BACKEND / "config" / "routes.json").read_text(encoding="utf-8"))
    return [Route.model_validate({"trips_observed": 0, "hours_covered": [], **r}) for r in raw]


def _gemini(deadline: str, **extra):
    args = {"route_id": BUS29, "deadline": deadline, **extra}

    def handler(request):
        part = {"functionCall": {"name": "get_departure_curve", "args": args}}
        return httpx.Response(200, json={"candidates": [{"content": {"parts": [part]}}]})

    return httpx.MockTransport(handler)


def _curve(first: datetime, minutes: int, *, recommended: datetime | None, status="ok"):
    points = [
        CurvePoint(
            depart_at=first + timedelta(minutes=i),
            p_on_time=0.5,
            ci=(0.4, 0.6),
            arrive_p50=first + timedelta(minutes=i + 30),
            arrive_p90=first + timedelta(minutes=i + 40),
            n_trips=20,
        )
        for i in range(minutes + 1)
    ]
    return DepartureCurveResponse(
        points=points,
        recommended=Recommended(depart_at=recommended, p_on_time=0.92) if recommended else None,
        what_if=[],
        server_ms=0,
        data_quality=DataQuality(status=status, basis="stub basis"),
    )


def _ask(deadline: str, response: DepartureCurveResponse, now=SUNDAY_MORNING, **extra):
    requests: list[DepartureCurveRequest] = []

    def compute(req: DepartureCurveRequest) -> DepartureCurveResponse:
        requests.append(req)
        return response

    def no_live(route: Route) -> LiveResponse:
        raise AssertionError("live data is not used for a departure question")

    result = ask.answer_question(
        "I need to be at Tottenham Court Road by 5pm on Saturday 24 October",
        now=now,
        routes=_routes(),
        api_key="test-key",
        compute_curve=compute,
        get_live=no_live,
        transport=_gemini(deadline, **extra),
    )
    return result, requests


def test_dated_question_resolves_to_saturday_five_pm_london():
    # 17:00 BST on Sat 24 Oct is 16:00Z; asked on Sunday, so that time is in the past.
    curve = _curve(datetime(2026, 10, 24, 14, 30, tzinfo=UTC), 90, recommended=datetime(2026, 10, 24, 15, 22, tzinfo=UTC))
    result, requests = _ask("2026-10-24T17:00:00", curve)
    assert result.status == "ok"
    assert result.interpretation.route_id == BUS29
    assert result.interpretation.deadline == datetime(2026, 10, 24, 16, 0, tzinfo=UTC)
    assert requests[0].deadline == datetime(2026, 10, 24, 16, 0, tzinfo=UTC)
    assert "Leave by 16:22" in result.answer  # 15:22Z in London time
    assert "92%" in result.answer


def test_answer_names_route_assumed_walks_and_past_deadline():
    curve = _curve(datetime(2026, 10, 24, 14, 30, tzinfo=UTC), 90, recommended=datetime(2026, 10, 24, 15, 22, tzinfo=UTC))
    answer = _ask("2026-10-24T17:00:00", curve)[0].answer
    assert "Mornington Crescent" in answer
    assert "Tottenham Court Road" in answer
    assert "5-minute walks at each end" in answer
    assert "already passed" in answer
    assert "Sat 24 Oct" in answer


def test_future_deadline_is_not_flagged_as_past():
    curve = _curve(datetime(2026, 10, 25, 14, 30, tzinfo=UTC), 90, recommended=datetime(2026, 10, 25, 15, 22, tzinfo=UTC))
    answer = _ask("2026-10-25T17:00:00", curve)[0].answer
    assert "already passed" not in answer


def test_different_walk_times_are_stated():
    curve = _curve(datetime(2026, 10, 25, 14, 30, tzinfo=UTC), 90, recommended=datetime(2026, 10, 25, 15, 22, tzinfo=UTC))
    answer = _ask("2026-10-25T17:00:00", curve, walk_to_min=8, walk_from_min=3)[0].answer
    assert "8-minute walk to the stop" in answer
    assert "3 minutes from the last stop" in answer


def test_no_recommendation_states_the_window_bounds_not_next_n_minutes():
    # Points run 14:30Z-15:30Z, which is 15:30-16:30 London (BST).
    curve = _curve(datetime(2026, 10, 24, 14, 30, tzinfo=UTC), 60, recommended=None, status="low_data")
    answer = _ask("2026-10-24T17:00:00", curve)[0].answer
    assert "between 15:30 and 16:30" in answer
    assert "in the next" not in answer
    assert "Mornington Crescent" in answer


def test_insufficient_data_still_names_the_route():
    empty = DepartureCurveResponse(
        points=[], recommended=None, what_if=[], server_ms=0,
        data_quality=DataQuality(status="insufficient_data", basis="stub basis"),
    )
    answer = _ask("2026-10-25T17:00:00", empty)[0].answer
    assert answer.startswith("I don't have enough recorded data to say.")
    assert "Mornington Crescent" in answer
    assert "stub basis" in answer
