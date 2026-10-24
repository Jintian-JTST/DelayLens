"""DelayLens model: empirical replay over recorded trips (PLAN.md section 4).

All times are UTC epoch seconds (int64). Local clocks repeat 01:00-02:00 on
Sun 25 Oct; UTC never does.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

import numpy as np

SECONDS_PER_MIN = 60


@dataclass(frozen=True)
class Segments:
    """Observed trips on one route, sorted by departure from the origin stop."""

    vehicle_id: np.ndarray  # str, one per trip
    t_origin: np.ndarray  # int64 UTC epoch seconds at origin O
    t_dest: np.ndarray  # int64 UTC epoch seconds at destination D

    def __post_init__(self) -> None:
        n = len(self.t_origin)
        if len(self.vehicle_id) != n or len(self.t_dest) != n:
            raise ValueError("vehicle_id, t_origin and t_dest must have equal length")
        if np.any(self.t_dest <= self.t_origin):
            raise ValueError("every trip needs t_dest > t_origin")
        if np.any(np.diff(self.t_origin) < 0):
            raise ValueError("trips must be sorted by t_origin")

    def __len__(self) -> int:
        return len(self.t_origin)


def to_epoch(dt: datetime) -> int:
    """UTC epoch seconds for a timezone-aware datetime."""
    if dt.tzinfo is None or dt.utcoffset() is None:
        raise ValueError("datetime must be timezone-aware")
    return int(dt.timestamp())


def synthetic_segments(
    start: datetime,
    end: datetime,
    *,
    headway_min: float = 10.0,
    ride_min: float = 20.0,
    headway_jitter_min: float = 0.0,
    ride_jitter_min: float = 0.0,
    seed: int = 0,
) -> Segments:
    """Timetabled trips leaving O every `headway_min` from `start` until before `end`.

    With zero jitter the timetable is exact, so replay results can be checked by
    hand. Jitter shifts each departure uniformly by up to +/- `headway_jitter_min`
    and adds normal noise (sd `ride_jitter_min`) to each ride, floored at 1 min.
    """
    t0, t1 = to_epoch(start), to_epoch(end)
    headway_s = round(headway_min * SECONDS_PER_MIN)
    if headway_s <= 0 or ride_min <= 0 or t1 <= t0:
        raise ValueError("need headway_min > 0, ride_min > 0 and end > start")

    rng = np.random.default_rng(seed)
    t_origin = np.arange(t0, t1, headway_s, dtype=np.int64)
    if headway_jitter_min > 0:
        shift = rng.uniform(-headway_jitter_min, headway_jitter_min, len(t_origin))
        t_origin = np.sort(t_origin + np.round(shift * SECONDS_PER_MIN).astype(np.int64))

    ride_s = np.full(len(t_origin), ride_min * SECONDS_PER_MIN)
    if ride_jitter_min > 0:
        ride_s = ride_s + rng.normal(0.0, ride_jitter_min * SECONDS_PER_MIN, len(t_origin))
    ride_s = np.maximum(np.round(ride_s), SECONDS_PER_MIN).astype(np.int64)

    vehicle_id = np.array([f"SYN{i:04d}" for i in range(len(t_origin))])
    return Segments(vehicle_id=vehicle_id, t_origin=t_origin, t_dest=t_origin + ride_s)


SECONDS_PER_DAY = 86_400
BOARD_AFTER_S = SECONDS_PER_MIN  # catch the first vehicle >= 1 min after reaching the stop


@dataclass(frozen=True)
class Curve:
    """One row per candidate departure; times are UTC epoch seconds.

    Rows with no usable replay instant have p_on_time and arrivals NaN and
    n_trips 0; thresholds for low/insufficient data are applied on top.
    """

    depart_at: np.ndarray  # int64
    p_on_time: np.ndarray  # float
    arrive_p50: np.ndarray  # float
    arrive_p90: np.ndarray  # float
    n_trips: np.ndarray  # int, distinct vehicles behind each row


def replay_curve(
    segments: Segments,
    depart_at: np.ndarray,
    deadline: int,
    *,
    walk_to_min: float = 0.0,
    walk_from_min: float = 0.0,
    tod_window_min: int = 30,
) -> Curve:
    """Empirical replay (PLAN.md section 4.1) for many departures at once.

    For each departure d the user reaches O at s = d + walk_to. Every recorded
    instant s' at the same UTC time of day (+/- tod_window_min, 1-min steps, any
    recorded day) is replayed: take the first vehicle leaving O at or after
    s' + 1 min, so TT(s') = t_D - s' + walk_from. Instants with no later vehicle,
    or before the first recorded departure, are outside the data and dropped.
    """
    depart_at = np.asarray(depart_at, dtype=np.int64)
    walk_to_s = round(walk_to_min * SECONDS_PER_MIN)
    walk_from_s = round(walk_from_min * SECONDS_PER_MIN)
    reach = depart_at + walk_to_s  # (m,)

    # Same time of day on every recorded day, then the +/- window in 1-min steps.
    first, last = segments.t_origin[0], segments.t_origin[-1]
    k_lo = (first - reach.max()) // SECONDS_PER_DAY - 1
    k_hi = (last - reach.min()) // SECONDS_PER_DAY + 1
    days = np.arange(k_lo, k_hi + 1, dtype=np.int64) * SECONDS_PER_DAY
    steps = np.arange(-tod_window_min, tod_window_min + 1, dtype=np.int64) * SECONDS_PER_MIN
    offsets = (days[:, None] + steps[None, :]).ravel()
    instants = reach[:, None] + offsets[None, :]  # (m, k)

    idx = np.searchsorted(segments.t_origin, instants + BOARD_AFTER_S, side="left")
    valid = (idx < len(segments)) & (instants >= first)
    safe_idx = np.where(valid, idx, 0)

    travel = segments.t_dest[safe_idx] - instants + walk_from_s  # TT(s')
    arrive = np.where(valid, reach[:, None] + travel, np.nan)

    n_valid = valid.sum(axis=1)
    on_time = valid & (arrive <= deadline)
    with np.errstate(invalid="ignore", divide="ignore"):
        p = np.where(n_valid > 0, on_time.sum(axis=1) / n_valid, np.nan)

    has_rows = n_valid > 0
    p50 = np.full(len(depart_at), np.nan)
    p90 = np.full(len(depart_at), np.nan)
    if has_rows.any():
        p50[has_rows], p90[has_rows] = np.nanpercentile(arrive[has_rows], [50, 90], axis=1)

    # Distinct vehicles per row: sort trip indices, count changes (invalid -> -1).
    trips = np.sort(np.where(valid, idx, -1), axis=1)
    distinct = (np.diff(trips, axis=1) != 0) & (trips[:, 1:] >= 0)
    n_trips = distinct.sum(axis=1) + (trips[:, 0] >= 0)

    return Curve(depart_at=depart_at, p_on_time=p, arrive_p50=p50, arrive_p90=p90, n_trips=n_trips)


def departure_curve(
    segments: Segments,
    deadline: datetime,
    *,
    walk_to_min: float = 0.0,
    walk_from_min: float = 0.0,
    window_min: int = 90,
    tod_window_min: int = 30,
) -> Curve:
    """Curve from `deadline - window_min` to `deadline` at 1-min resolution (section 4.3)."""
    t = to_epoch(deadline)
    depart_at = t - np.arange(window_min, -1, -1, dtype=np.int64) * SECONDS_PER_MIN
    return replay_curve(
        segments,
        depart_at,
        t,
        walk_to_min=walk_to_min,
        walk_from_min=walk_from_min,
        tod_window_min=tod_window_min,
    )


def p_on_time(
    segments: Segments,
    depart_at: datetime,
    deadline: datetime,
    *,
    walk_to_min: float = 0.0,
    walk_from_min: float = 0.0,
    tod_window_min: int = 30,
) -> float:
    """P(arrive by `deadline` | leave at `depart_at`); NaN if no data covers it."""
    curve = replay_curve(
        segments,
        np.array([to_epoch(depart_at)]),
        to_epoch(deadline),
        walk_to_min=walk_to_min,
        walk_from_min=walk_from_min,
        tod_window_min=tod_window_min,
    )
    return float(curve.p_on_time[0])
