"""DelayLens model: empirical replay over inferred trip segments (PLAN.md section 4).

All instants are UTC epoch seconds (int64). Reference windows are taken in
Europe/London local time on explicitly chosen dates: by default only the query's
own date is replayed, so Saturday and Sunday are never pooled silently. The two
local 01:00 hours on Sun 25 Oct stay distinct because each is resolved to UTC.
"""

from __future__ import annotations

import csv
from collections import Counter
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path
from typing import Sequence
from zoneinfo import ZoneInfo

import numpy as np

LONDON = ZoneInfo("Europe/London")
SECONDS_PER_MIN = 60
BOARD_BUFFER_MIN = 1.0  # documented boarding buffer: first vehicle >= 1 min after reaching O

# Evidence policy (PLAN.md section 4): usable runs -> API data status.
LOW_DATA_MIN_RUNS = 5
OK_MIN_RUNS = 15

# Minimum segment handoff fields (PLAN.md section 3.5).
CSV_FIELDS = (
    "segment_id",
    "route_id",
    "vehicle_id",
    "origin_at",
    "destination_at",
    "travel_seconds",
    "inference_method",
    "quality",
    "source",
)
USABLE_QUALITY = "estimated"


@dataclass(frozen=True)
class Segments:
    """Deduplicated usable runs on one route, sorted by departure from origin O.

    `coverage` lists closed UTC intervals [start, end] in which recording was
    complete. Replay never looks across a gap: a vehicle that might have run
    during one is unknown, not late. It defaults to first..last departure.
    """

    segment_id: np.ndarray  # str, unique per canonical run
    vehicle_id: np.ndarray  # str
    t_origin: np.ndarray  # int64 UTC epoch seconds at O
    t_dest: np.ndarray  # int64 UTC epoch seconds at destination D
    coverage: np.ndarray | None = field(default=None)  # int64, shape (k, 2)

    def __post_init__(self) -> None:
        n = len(self.t_origin)
        if not (len(self.segment_id) == len(self.vehicle_id) == len(self.t_dest) == n):
            raise ValueError("segment_id, vehicle_id, t_origin and t_dest must have equal length")
        if np.any(self.t_dest <= self.t_origin):
            raise ValueError("every segment needs t_dest > t_origin")
        if np.any(np.diff(self.t_origin) < 0):
            raise ValueError("segments must be sorted by t_origin")
        if len(np.unique(self.segment_id)) != n:
            raise ValueError("segment_id must be unique")

        if self.coverage is None:
            default = [[self.t_origin[0], self.t_origin[-1]]] if n else []
            object.__setattr__(self, "coverage", np.array(default, dtype=np.int64).reshape(-1, 2))
        cov = self.coverage
        if cov.ndim != 2 or cov.shape[1] != 2 or np.any(cov[:, 1] < cov[:, 0]):
            raise ValueError("coverage must be (k, 2) intervals with end >= start")
        if np.any(cov[1:, 0] <= cov[:-1, 1]):
            raise ValueError("coverage intervals must be sorted and non-overlapping")

    def __len__(self) -> int:
        return len(self.t_origin)


@dataclass(frozen=True)
class LoadReport:
    """What a segment CSV contained and why rows were left out of the model."""

    n_rows: int
    n_used: int
    excluded: dict[str, int]


def to_epoch(dt: datetime) -> int:
    """UTC epoch seconds for a timezone-aware datetime."""
    if dt.tzinfo is None or dt.utcoffset() is None:
        raise ValueError("datetime must be timezone-aware")
    return int(dt.timestamp())


def load_segments_csv(
    path: str | Path,
    route_id: str,
    coverage: Sequence[tuple[datetime, datetime]] | None = None,
) -> tuple[Segments, LoadReport]:
    """Read D's segment CSV for one route, keeping only usable estimated runs.

    Every excluded row is counted by reason; nothing is dropped silently.
    """
    excluded: Counter[str] = Counter()
    seen: set[str] = set()
    rows: list[tuple[str, str, int, int]] = []
    n_rows = 0

    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        missing = set(CSV_FIELDS) - set(reader.fieldnames or ())
        if missing:
            raise ValueError(f"segment CSV is missing columns: {sorted(missing)}")
        for row in reader:
            n_rows += 1
            if row["route_id"] != route_id:
                excluded["other_route"] += 1
                continue
            if row["quality"] != USABLE_QUALITY:
                excluded["not_estimated"] += 1
                continue
            if row["segment_id"] in seen:
                excluded["duplicate_segment_id"] += 1
                continue
            try:
                t_o = to_epoch(datetime.fromisoformat(row["origin_at"]))
                t_d = to_epoch(datetime.fromisoformat(row["destination_at"]))
                travel = int(float(row["travel_seconds"]))
            except ValueError:
                excluded["bad_timestamp"] += 1
                continue
            if t_d <= t_o:
                excluded["non_positive_duration"] += 1
                continue
            if abs((t_d - t_o) - travel) > 1:
                excluded["duration_mismatch"] += 1
                continue
            seen.add(row["segment_id"])
            rows.append((row["segment_id"], row["vehicle_id"], t_o, t_d))

    rows.sort(key=lambda r: r[2])
    cov = None
    if coverage is not None:
        cov = np.array([[to_epoch(a), to_epoch(b)] for a, b in coverage], dtype=np.int64)
        cov = cov.reshape(-1, 2)
    segments = Segments(
        segment_id=np.array([r[0] for r in rows], dtype=str),
        vehicle_id=np.array([r[1] for r in rows], dtype=str),
        t_origin=np.array([r[2] for r in rows], dtype=np.int64),
        t_dest=np.array([r[3] for r in rows], dtype=np.int64),
        coverage=cov,
    )
    return segments, LoadReport(n_rows=n_rows, n_used=len(rows), excluded=dict(excluded))


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
    """Timetabled runs leaving O every `headway_min` from `start` until before `end`.

    Coverage is the whole [start, end] recording. With zero jitter the timetable
    is exact, so replay results can be checked by hand. Jitter shifts each
    departure uniformly by up to +/- `headway_jitter_min` and adds normal noise
    (sd `ride_jitter_min`) to each ride, floored at 1 min.
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

    n = len(t_origin)
    return Segments(
        segment_id=np.array([f"SYN-{i:05d}" for i in range(n)]),
        vehicle_id=np.array([f"SYN{i % 12:02d}" for i in range(n)]),  # a fleet of 12 buses
        t_origin=t_origin,
        t_dest=t_origin + ride_s,
        coverage=np.array([[t0, t1]], dtype=np.int64),
    )


def evidence_status(n_runs: np.ndarray) -> np.ndarray:
    """0-4 runs: insufficient_data; 5-14: low_data; 15+: ok (PLAN.md section 4)."""
    n_runs = np.asarray(n_runs)
    return np.where(
        n_runs < LOW_DATA_MIN_RUNS,
        "insufficient_data",
        np.where(n_runs < OK_MIN_RUNS, "low_data", "ok"),
    )


@dataclass(frozen=True)
class Curve:
    """One row per candidate departure; instants are UTC epoch seconds.

    p_on_time and arrivals are NaN where status is insufficient_data: the counts
    are reported, the probability is not. Uncertainty bands and the advisor are
    applied on top of this.
    """

    depart_at: np.ndarray  # int64
    p_on_time: np.ndarray  # float
    arrive_p50: np.ndarray  # float
    arrive_p90: np.ndarray  # float
    n_trips: np.ndarray  # int, distinct usable runs (segment_id) behind each row
    n_vehicles: np.ndarray  # int, distinct vehicle IDs among those runs
    n_steps: np.ndarray  # int, eligible replay instants
    n_censored: np.ndarray  # int, replay instants outside coverage or with no observed next run
    status: np.ndarray  # str, see evidence_status


def reference_instants(
    reach: np.ndarray,
    reference_dates: Sequence[date] | None,
    tod_window_min: int,
) -> np.ndarray:
    """Replay instants (m, k): the same London local time on each reference date,
    +/- tod_window_min in 1-min steps of elapsed time.

    With no reference dates, each query is replayed only on its own date. The
    query's DST fold is kept, so 01:30 BST and 01:30 GMT on Sun 25 Oct differ.
    """
    reach = np.asarray(reach, dtype=np.int64)
    if reference_dates is None:
        base = reach[:, None]
    else:
        base = np.empty((len(reach), len(reference_dates)), dtype=np.int64)
        for i, e in enumerate(reach):
            local_time = datetime.fromtimestamp(int(e), LONDON).time()  # keeps fold
            for j, d in enumerate(reference_dates):
                base[i, j] = to_epoch(datetime.combine(d, local_time, tzinfo=LONDON))
    steps = np.arange(-tod_window_min, tod_window_min + 1, dtype=np.int64) * SECONDS_PER_MIN
    return (base[:, :, None] + steps[None, None, :]).reshape(len(reach), -1)


def _distinct_per_row(codes: np.ndarray, valid: np.ndarray) -> np.ndarray:
    """Count distinct non-negative codes per row, ignoring invalid entries."""
    if codes.shape[1] == 0:
        return np.zeros(codes.shape[0], dtype=np.int64)
    s = np.sort(np.where(valid, codes, -1), axis=1)
    changes = (np.diff(s, axis=1) != 0) & (s[:, 1:] >= 0)
    return changes.sum(axis=1) + (s[:, 0] >= 0)


def replay_curve(
    segments: Segments,
    depart_at: np.ndarray,
    deadline: int,
    *,
    walk_to_min: float = 0.0,
    walk_from_min: float = 0.0,
    tod_window_min: int = 30,
    board_buffer_min: float = BOARD_BUFFER_MIN,
    reference_dates: Sequence[date] | None = None,
) -> Curve:
    """Empirical replay (PLAN.md section 4) for many departures at once.

    For departure d the user reaches O at s = d + walk_to. Each reference instant
    s' boards the first run leaving O at or after s' + board_buffer, giving
    TT(s') = t_D - s' + walk_from and arrival s + TT(s'). An instant is censored
    unless its boarding time and that run's departure lie in the same coverage
    interval: the recording edge and capture gaps are unknown, not late.
    """
    depart_at = np.asarray(depart_at, dtype=np.int64)
    walk_to_s = round(walk_to_min * SECONDS_PER_MIN)
    walk_from_s = round(walk_from_min * SECONDS_PER_MIN)
    buffer_s = round(board_buffer_min * SECONDS_PER_MIN)
    reach = depart_at + walk_to_s

    instants = reference_instants(reach, reference_dates, tod_window_min)  # (m, k)
    board = instants + buffer_s

    cov = segments.coverage
    ci = np.searchsorted(cov[:, 0], board, side="right") - 1
    safe_ci = np.clip(ci, 0, max(len(cov) - 1, 0))
    if len(cov):
        # Runs before `board` are uncatchable anyway, so only boarding must be covered.
        cov_end = cov[safe_ci, 1]
        in_cov = (ci >= 0) & (board <= cov_end)
    else:
        cov_end = np.zeros_like(board)
        in_cov = np.zeros(board.shape, dtype=bool)

    idx = np.searchsorted(segments.t_origin, board, side="left")
    safe_idx = np.clip(idx, 0, max(len(segments) - 1, 0))
    found = idx < len(segments)
    if len(segments):
        found &= segments.t_origin[safe_idx] <= cov_end
    valid = in_cov & found

    if len(segments):
        travel = segments.t_dest[safe_idx] - instants + walk_from_s
    else:
        travel = np.zeros_like(instants)
    arrive = np.where(valid, reach[:, None] + travel, np.nan)

    n_steps = valid.sum(axis=1)
    _, vehicle_codes = np.unique(segments.vehicle_id, return_inverse=True)
    n_trips = _distinct_per_row(np.where(valid, safe_idx, -1), valid)
    n_vehicles = _distinct_per_row(
        vehicle_codes[safe_idx] if len(segments) else safe_idx, valid
    )
    status = evidence_status(n_trips)

    shown = status != "insufficient_data"
    p = np.full(len(depart_at), np.nan)
    p50 = np.full(len(depart_at), np.nan)
    p90 = np.full(len(depart_at), np.nan)
    if shown.any():
        on_time = valid[shown] & (arrive[shown] <= deadline)
        p[shown] = on_time.sum(axis=1) / n_steps[shown]
        p50[shown], p90[shown] = np.nanpercentile(arrive[shown], [50, 90], axis=1)

    return Curve(
        depart_at=depart_at,
        p_on_time=p,
        arrive_p50=p50,
        arrive_p90=p90,
        n_trips=n_trips,
        n_vehicles=n_vehicles,
        n_steps=n_steps,
        n_censored=instants.shape[1] - n_steps,
        status=status,
    )


def departure_curve(
    segments: Segments,
    deadline: datetime,
    *,
    walk_to_min: float = 0.0,
    walk_from_min: float = 0.0,
    window_min: int = 90,
    tod_window_min: int = 30,
    board_buffer_min: float = BOARD_BUFFER_MIN,
    reference_dates: Sequence[date] | None = None,
) -> Curve:
    """Curve from `deadline - window_min` to `deadline` at 1-min resolution."""
    t = to_epoch(deadline)
    depart_at = t - np.arange(window_min, -1, -1, dtype=np.int64) * SECONDS_PER_MIN
    return replay_curve(
        segments,
        depart_at,
        t,
        walk_to_min=walk_to_min,
        walk_from_min=walk_from_min,
        tod_window_min=tod_window_min,
        board_buffer_min=board_buffer_min,
        reference_dates=reference_dates,
    )


def p_on_time(
    segments: Segments,
    depart_at: datetime,
    deadline: datetime,
    **kwargs,
) -> float:
    """P(arrive by `deadline` | leave at `depart_at`); NaN under insufficient_data."""
    curve = replay_curve(segments, np.array([to_epoch(depart_at)]), to_epoch(deadline), **kwargs)
    return float(curve.p_on_time[0])
