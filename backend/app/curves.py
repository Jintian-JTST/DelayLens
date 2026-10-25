"""Map M's model output (app/model.py) onto the API contract (PLAN.md section 6.3).

B owns this file; probability, band and advice logic stay in the model. `ci` is
M's 90% run bootstrap on ok rows. The model gives no band for low_data rows, but
the contract and frontend need one, so those get a wider 90% Wilson interval over
distinct runs.
"""

import math
from datetime import UTC, date, datetime
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

# Time-of-day window (+/- minutes) for reference runs. Shared with calibration so
# the backtest scores the same model the API serves.
TOD_WINDOW_MIN = 60


# Polls further apart than this many typical intervals split the coverage,
# matching D's exporter (tasks/model.md, load_handoff).
POLL_GAP_FACTOR = 1.5


def poll_coverage(poll_times: list[datetime]) -> np.ndarray | None:
    """Closed UTC intervals of continuous recording, split at missed polls."""
    if len(poll_times) < 2:
        return None
    t = np.array([model.to_epoch(x) for x in sorted(poll_times)], dtype=np.int64)
    gaps = np.diff(t)
    split = np.flatnonzero(gaps > POLL_GAP_FACTOR * float(np.median(gaps)))
    starts = np.concatenate(([t[0]], t[split + 1]))
    ends = np.concatenate((t[split], [t[-1]]))
    return np.column_stack((starts, ends))


def to_segments(
    rows: list[db.Segment],
    origin_events: list[db.OriginEvent] | None = None,
    poll_times: list[datetime] | None = None,
) -> model.Segments:
    """One route's usable runs in the model's input format, deduplicated.

    Origin departures with no usable run become unconfirmed departures, and
    coverage comes from the poll ledger, clipped to when this route was first
    seen (routes can be added after recording started).
    """
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

    events = origin_events or []
    unconfirmed = np.sort(np.array(
        [
            model.to_epoch(e.observed_at)
            for e in events
            if f"{e.vehicle_id}|{e.episode_started_at.isoformat()}" not in seen
        ],
        dtype=np.int64,
    ))

    coverage = poll_coverage(poll_times or [])
    first_seen = [model.to_epoch(e.observed_at) for e in events] + [k[2] for k in kept]
    if coverage is not None and first_seen:
        start = min(first_seen)
        coverage = coverage[coverage[:, 1] >= start]
        if len(coverage):
            coverage[0, 0] = max(coverage[0, 0], start)
        else:
            coverage = None

    return model.Segments(
        segment_id=np.array([k[0] for k in kept], dtype=str),
        vehicle_id=np.array([k[1] for k in kept], dtype=str),
        t_origin=np.array([k[2] for k in kept], dtype=np.int64),
        t_dest=np.array([k[3] for k in kept], dtype=np.int64),
        coverage=coverage,
        unconfirmed_departures=unconfirmed,
    )


def _wilson(p: float, n: int) -> tuple[float, float]:
    if n <= 0:
        return (0.0, 1.0)
    denom = 1 + Z_90**2 / n
    centre = (p + Z_90**2 / (2 * n)) / denom
    half = Z_90 * math.sqrt(p * (1 - p) / n + Z_90**2 / (4 * n**2)) / denom
    return (round(max(0.0, centre - half), 4), round(min(1.0, centre + half), 4))


def _band(curve: model.Curve, i: int, p: float) -> tuple[float, float]:
    low, high = float(curve.ci_low[i]), float(curve.ci_high[i])
    if math.isnan(low) or math.isnan(high):
        return _wilson(p, int(curve.n_trips[i]))
    return (round(low, 4), round(high, 4))


def _utc(epoch: float) -> datetime:
    return datetime.fromtimestamp(float(epoch), UTC)


def _reference_note(deadline: datetime, reference_date: date) -> str:
    asked = deadline.astimezone(LONDON).date()
    why = (
        "same weekday"
        if reference_date.weekday() == asked.weekday()
        else "most recent recorded day; no same-weekday recordings yet"
    )
    return (
        f"No trips recorded for {asked:%a %d %b} near this time, so this replays "
        f"{reference_date:%a %d %b} at the same London time ({why})."
    )


def _basis(
    segments: model.Segments,
    snapshot_label: str | None = None,
    reference_note: str | None = None,
) -> str:
    n = len(segments)
    if n == 0:
        return "No trips recorded on this route yet."
    first = datetime.fromtimestamp(int(segments.t_origin[0]), LONDON)
    last = datetime.fromtimestamp(int(segments.t_origin[-1]), LONDON)
    span = f"{first:%a %d %b %H:%M} - {last:%a %d %b %H:%M}"
    text = (
        f"Based on {n} trips recorded on this route ({span}, London time), replaying "
        f"±{TOD_WINDOW_MIN} min around each departure. Arrivals are estimated "
        "from TfL predictions, not measured; not yet calibrated."
    )
    if reference_note:
        text = f"{reference_note} {text}"
    return f"{text} {snapshot_label}" if snapshot_label else text


def journey_basis(
    leg_labels: list[str],
    leg_segments: list[model.Segments],
    transfer_min: float,
    snapshot_label: str | None = None,
    reference_note: str | None = None,
) -> str:
    """Data note for a journey: trips behind each leg and, for a change, how the
    legs are combined."""
    legs = "; ".join(
        f"{label} ({len(seg)} trips recorded)"
        for label, seg in zip(leg_labels, leg_segments, strict=True)
    )
    if len(leg_labels) == 1:
        text = f"Direct: {legs}, replaying ±{TOD_WINDOW_MIN} min around each departure."
    else:
        text = (
            f"One change: {legs}. Both legs are replayed on the same recorded day "
            f"(±{TOD_WINDOW_MIN} min), so a late first bus meets the second leg's real "
            f"departures; the change allows {transfer_min:g} min plus the boarding "
            "buffer, and evidence counts the fewer runs of either leg."
        )
    text += " Arrivals are estimated from TfL predictions, not measured; not yet calibrated."
    if reference_note:
        text = f"{reference_note} {text}"
    return f"{text} {snapshot_label}" if snapshot_label else text


def build_response(
    curve: model.Curve,
    req: DepartureCurveRequest,
    segments: model.Segments,
    snapshot_label: str | None = None,
    reference_date: date | None = None,
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
                ci=_band(curve, i, p),
                arrive_p50=_utc(curve.arrive_p50[i]),
                arrive_p90=_utc(curve.arrive_p90[i]),
                n_trips=int(curve.n_trips[i]),
            )
        )
        statuses.append(str(curve.status[i]))

    advice = model.recommend(curve, req.tolerance)
    best = (
        Recommended(depart_at=_utc(advice.depart_at), p_on_time=round(advice.p_on_time, 4))
        if advice.depart_at is not None and advice.p_on_time is not None
        else None
    )
    what_if = (
        [
            WhatIf(delay_min=delay, p_on_time=round(p, 4), delta=round(change, 4))
            for delay, p, change in model.what_if(curve, advice.depart_at, WHAT_IF_MIN)
            if p is not None and change is not None
        ]
        if advice.depart_at is not None
        else []
    )

    if not points:
        status = "insufficient_data"
    elif "low_data" in statuses:
        status = "low_data"
    else:
        status = "ok"
    return DepartureCurveResponse(
        points=points,
        recommended=best,
        what_if=what_if,
        data_quality=DataQuality(
            status=status,
            basis=_basis(
                segments,
                snapshot_label,
                _reference_note(req.deadline, reference_date) if reference_date else None,
            ),
        ),
        server_ms=0.0,
    )
