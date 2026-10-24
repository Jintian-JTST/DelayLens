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


def p_on_time(
    segments: Segments,
    depart_at: datetime,
    deadline: datetime,
    *,
    walk_to_min: float = 0.0,
    walk_from_min: float = 0.0,
    tod_window_min: int = 30,
) -> float:
    """P(arrive by `deadline` | leave at `depart_at`) by empirical replay (section 4.1)."""
    raise NotImplementedError("empirical replay is the next task (PLAN.md section 8, Sat 15:00)")
