"""The Ask test set (PLAN.md section 5): ~20 phrasings checked against Gemini.

The structural checks always run. The Gemini checks call the real API and are
opt-in: set DELAYLENS_RUN_GEMINI_TESTS=1 with GEMINI_API_KEY in backend/.env.
"""

import json
import os
import time
from datetime import UTC, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest
from dotenv import load_dotenv

from app import ask
from app.schemas import (
    DataQuality,
    DepartureCurveRequest,
    DepartureCurveResponse,
    LiveArrival,
    LiveResponse,
    Route,
)

BACKEND = Path(__file__).resolve().parent.parent
CASES = json.loads((BACKEND / "tests" / "ask_cases.json").read_text(encoding="utf-8"))
LONDON = ZoneInfo("Europe/London")
STATUSES = {"ok", "unsupported_route", "unclear", "gemini_unavailable"}
GEMINI_PACING_S = 5


def _routes() -> list[Route]:
    raw = json.loads((BACKEND / "config" / "routes.json").read_text(encoding="utf-8"))
    return [Route.model_validate({"trips_observed": 0, "hours_covered": [], **r}) for r in raw]


def test_case_file_is_consistent():
    route_ids = {r.route_id for r in _routes()}
    ids = [c["id"] for c in CASES["cases"]]
    assert len(ids) >= 20
    assert len(ids) == len(set(ids))
    for case in CASES["cases"]:
        expect = case["expect"]
        assert expect["status"] in STATUSES
        for rid in [expect.get("route_id"), *expect.get("route_id_in", [])]:
            assert rid is None or rid in route_ids, case["id"]


def _no_curve(req: DepartureCurveRequest) -> DepartureCurveResponse:
    # Only Gemini's interpretation is under test here, not the model.
    return DepartureCurveResponse(
        points=[], recommended=None, what_if=[], server_ms=0,
        data_quality=DataQuality(status="insufficient_data", basis="test stub"),
    )


def _fake_live(route: Route) -> LiveResponse:
    now = datetime.now(UTC)
    return LiveResponse(
        route_id=route.route_id,
        fetched_at=now,
        arrivals=[LiveArrival(vehicle_id="T1", line_id=route.line_id,
                              time_to_station_s=240, expected_arrival=now)],
    )


def _local(dt: datetime | None) -> str | None:
    return dt.astimezone(LONDON).strftime("%Y-%m-%dT%H:%M") if dt else None


@pytest.mark.live_gemini
@pytest.mark.skipif(
    os.getenv("DELAYLENS_RUN_GEMINI_TESTS") != "1",
    reason="Set DELAYLENS_RUN_GEMINI_TESTS=1 to call the real Gemini API",
)
@pytest.mark.parametrize("case", CASES["cases"], ids=lambda c: c["id"])
def test_gemini_interprets_case(case):
    time.sleep(GEMINI_PACING_S)  # stay under the free tier's requests-per-minute limit
    load_dotenv(BACKEND / ".env")
    result = ask.answer_question(
        case["question"],
        now=datetime.fromisoformat(CASES["now"]),
        routes=_routes(),
        api_key=os.getenv("GEMINI_API_KEY", ""),
        compute_curve=_no_curve,
        get_live=_fake_live,
    )
    expect = case["expect"]
    interp = result.interpretation
    assert result.status != "gemini_unavailable", "Gemini unreachable or overloaded"
    assert result.status == expect["status"], result.answer
    if "route_id" in expect:
        assert interp.route_id == expect["route_id"]
    if "route_id_in" in expect:
        assert interp.route_id in expect["route_id_in"]
    if "deadline_local" in expect:
        assert _local(interp.deadline) == expect["deadline_local"]
    if "tolerance_range" in expect:
        lo, hi = expect["tolerance_range"]
        assert interp.tolerance is not None and lo <= interp.tolerance <= hi
    if "walk_to_min" in expect:
        assert interp.walk_to_min == expect["walk_to_min"]
    if "compare_local" in expect:
        assert [_local(d) for d in interp.compare or []] == expect["compare_local"]
    if "answer_contains" in expect:
        assert expect["answer_contains"] in result.answer
