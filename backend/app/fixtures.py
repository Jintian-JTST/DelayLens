"""Clearly labelled fixture data so M and F can build before real data flows.

Remove before judging (PLAN.md §7). Nothing here is real or live.
"""

import json
import math
from datetime import UTC, datetime, timedelta
from pathlib import Path

from app.schemas import (
    CurvePoint,
    DataQuality,
    DepartureCurveRequest,
    DepartureCurveResponse,
    Recommended,
    Route,
    WhatIf,
)

FIXTURES_DIR = Path(__file__).resolve().parent.parent / "fixtures"
FIXTURE_BASIS = "FIXTURE DATA: not real observations"


def load_routes() -> list[Route]:
    raw = json.loads((FIXTURES_DIR / "routes.json").read_text(encoding="utf-8"))
    return [Route.model_validate(r) for r in raw]


def _p_on_time(minutes_before_deadline: float, journey_min: float) -> float:
    """Logistic fall-off: leaving later than (journey + 10 min slack) is risky."""
    slack = minutes_before_deadline - (journey_min + 10)
    return 1 / (1 + math.exp(-slack / 3))


def fixture_curve(req: DepartureCurveRequest) -> DepartureCurveResponse:
    deadline = req.deadline.astimezone(UTC)
    journey = 30 + req.walk_to_min + req.walk_from_min
    points: list[CurvePoint] = []
    for m in range(req.window_min, -1, -1):
        depart = deadline - timedelta(minutes=m)
        p = _p_on_time(m, journey)
        half = 0.05 * (1 - abs(2 * p - 1)) + 0.01
        arrive50 = depart + timedelta(minutes=journey + 10)
        points.append(
            CurvePoint(
                depart_at=depart,
                p_on_time=round(p, 4),
                ci=(round(max(0, p - half), 4), round(min(1, p + half), 4)),
                arrive_p50=arrive50,
                arrive_p90=arrive50 + timedelta(minutes=8),
                n_trips=40,
            )
        )
    ok = [pt for pt in points if 1 - pt.p_on_time <= req.tolerance]
    best = ok[-1] if ok else None
    by_depart = {pt.depart_at: pt for pt in points}
    what_if: list[WhatIf] = []
    if best:
        for d in (5, 10, 15):
            later = by_depart.get(best.depart_at + timedelta(minutes=d))
            p = later.p_on_time if later else 0.0
            what_if.append(
                WhatIf(delay_min=d, p_on_time=p, delta=round(p - best.p_on_time, 4))
            )
    return DepartureCurveResponse(
        points=points,
        recommended=(
            Recommended(depart_at=best.depart_at, p_on_time=best.p_on_time) if best else None
        ),
        what_if=what_if,
        data_quality=DataQuality(status="ok", basis=FIXTURE_BASIS),
        server_ms=0.0,
    )


def now_utc() -> datetime:
    return datetime.now(UTC)
