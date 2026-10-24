"""Map M's model output (app/model.py) onto the API contract (PLAN.md section 6.3).

B owns this file; probability logic stays in the model. Until M's bootstrap band
lands, `ci` is a provisional 90% Wilson interval over distinct runs.
"""

import math
from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

import numpy as np

from app import db, model
from app.schemas import (
    CurvePoint,
    DataQuality,
    DepartureCurveRequest,
    DepartureCurveResponse,
    Recommended,
    WhatIf,
)

LONDON = ZoneInfo("Europe/London")
Z_90 = 1.645
WHAT_IF_MIN = (5, 10, 15)


def to_segments(rows: list[db.Segment]) -> model.Segments:
    """Usable runs for one route in the model's input format, deduplicated."""
    seen: set[str] = set()
    kept: list[tuple[str, str, int, int]] = []
    for row in sorted(rows, key=lambda r: r.origin_observed_at):
        key = f"{row.vehicle_id}|{row.origin_episode_started_at.isoformat()}"
        t_o = model.to_epoch(row.origin_observed_at)
        t_d = model.to_epoch(row.destination_observed_at)
        if key in seen or t_d <= t_o:
            continue
        seen.add(key)
        kept.append((key, row.vehicle_id, t_o, t_d))
    return model.Segments(
        segment_id=np.array([k[0] for k in kept], dtype=str),
        vehicle_id=np.array([k[1] for k in kept], dtype=str),
        t_origin=np.array([k[2] for k in kept], dtype=np.int64),
        t_dest=np.array([k[3] for k in kept], dtype=np.int64),
    )


def _wilson(p: float, n: int) -> tuple[float, float]:
    if n <= 0:
        return (0.0, 1.0)
    denom = 1 + Z_90**2 / n
    centre = (p + Z_90**2 / (2 * n)) / denom
    half = Z_90 * math.sqrt(p * (1 - p) / n + Z_90**2 / (4 * n**2)) / denom
    return (round(max(0.0, centre - half), 4), round(min(1.0, centre + half), 4))


def _utc(epoch: float) -> datetime:
    return datetime.fromtimestamp(float(epoch), UTC)


def _basis(segments: model.Segments) -> str:
    n = len(segments)
    if n == 0:
        return "No trips recorded on this route yet."
    first = datetime.fromtimestamp(int(segments.t_origin[0]), LONDON)
    last = datetime.fromtimestamp(int(segments.t_origin[-1]), LONDON)
    span = f"{first:%a %d %b %H:%M} - {last:%a %d %b %H:%M}"
    return (
        f"Based on {n} recorded trips ({span}, London time). Arrivals are estimated "
        "from TfL predictions, not measured; not yet calibrated."
    )


def build_response(
    curve: model.Curve, req: DepartureCurveRequest, segments: model.Segments
) -> DepartureCurveResponse:
    points: list[CurvePoint] = []
    statuses: list[str] = []
    for i in range(len(curve.depart_at)):
        p = float(curve.p_on_time[i])
        if math.isnan(p):
            continue  # insufficient_data: the model reports counts, not a probability
        points.append(
            CurvePoint(
                depart_at=_utc(curve.depart_at[i]),
                p_on_time=round(p, 4),
                ci=_wilson(p, int(curve.n_trips[i])),
                arrive_p50=_utc(curve.arrive_p50[i]),
                arrive_p90=_utc(curve.arrive_p90[i]),
                n_trips=int(curve.n_trips[i]),
            )
        )
        statuses.append(str(curve.status[i]))

    # Advisor policy from tasks/model.md: recommend only from rows with status ok.
    eligible = [
        pt for pt, st in zip(points, statuses, strict=True)
        if st == "ok" and 1 - pt.p_on_time <= req.tolerance
    ]
    best = eligible[-1] if eligible else None
    what_if: list[WhatIf] = []
    if best is not None:
        by_depart = {pt.depart_at: pt for pt in points}
        for delay in WHAT_IF_MIN:
            later = by_depart.get(best.depart_at + timedelta(minutes=delay))
            if later is not None:
                what_if.append(
                    WhatIf(
                        delay_min=delay,
                        p_on_time=later.p_on_time,
                        delta=round(later.p_on_time - best.p_on_time, 4),
                    )
                )

    if not points:
        status = "insufficient_data"
    elif "low_data" in statuses:
        status = "low_data"
    else:
        status = "ok"
    return DepartureCurveResponse(
        points=points,
        recommended=Recommended(depart_at=best.depart_at, p_on_time=best.p_on_time) if best else None,
        what_if=what_if,
        data_quality=DataQuality(status=status, basis=_basis(segments)),
        server_ms=0.0,
    )
