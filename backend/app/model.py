"""DelayLens model: empirical replay over inferred trip segments (PLAN.md section 4).

All instants are UTC epoch seconds (int64). Reference windows are taken in
Europe/London local time on explicitly chosen dates: by default only the query's
own date is replayed, so Saturday and Sunday are never pooled silently. The two
local 01:00 hours on Sun 25 Oct stay distinct because each is resolved to UTC.
"""

from __future__ import annotations

import csv
import json
from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np

LONDON = ZoneInfo("Europe/London")
SECONDS_PER_MIN = 60
BOARD_BUFFER_MIN = (
    1.0  # documented boarding buffer: first vehicle >= 1 min after reaching O
)

# Evidence policy (PLAN.md section 4): usable runs -> API data status.
LOW_DATA_MIN_RUNS = 5
OK_MIN_RUNS = 15
N_BOOT = 200  # bootstrap resamples of whole runs for the 90% band
DEFAULT_TOLERANCE = 0.10  # advisor: accept up to 10% empirical chance of being late

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

    `unconfirmed_departures` are observed departures from O with no usable
    segment (uncertain events, or runs not yet seen at D). Such a bus was
    catchable, so replay instants that would board it are censored rather than
    skipped to the next usable run, which would overstate the wait.
    """

    segment_id: np.ndarray  # str, unique per canonical run
    vehicle_id: np.ndarray  # str
    t_origin: np.ndarray  # int64 UTC epoch seconds at O
    t_dest: np.ndarray  # int64 UTC epoch seconds at destination D
    coverage: np.ndarray | None = field(default=None)  # int64, shape (k, 2)
    unconfirmed_departures: np.ndarray | None = field(default=None)  # int64, sorted

    def __post_init__(self) -> None:
        n = len(self.t_origin)
        if not (len(self.segment_id) == len(self.vehicle_id) == len(self.t_dest) == n):
            raise ValueError(
                "segment_id, vehicle_id, t_origin and t_dest must have equal length"
            )
        if np.any(self.t_dest <= self.t_origin):
            raise ValueError("every segment needs t_dest > t_origin")
        if np.any(np.diff(self.t_origin) < 0):
            raise ValueError("segments must be sorted by t_origin")
        if len(np.unique(self.segment_id)) != n:
            raise ValueError("segment_id must be unique")

        if self.coverage is None:
            default = [[self.t_origin[0], self.t_origin[-1]]] if n else []
            object.__setattr__(
                self, "coverage", np.array(default, dtype=np.int64).reshape(-1, 2)
            )
        cov = self.coverage
        if cov.ndim != 2 or cov.shape[1] != 2 or np.any(cov[:, 1] < cov[:, 0]):
            raise ValueError("coverage must be (k, 2) intervals with end >= start")
        if np.any(cov[1:, 0] <= cov[:-1, 1]):
            raise ValueError("coverage intervals must be sorted and non-overlapping")

        if self.unconfirmed_departures is None:
            object.__setattr__(
                self, "unconfirmed_departures", np.array([], dtype=np.int64)
            )
        if np.any(np.diff(self.unconfirmed_departures) < 0):
            raise ValueError("unconfirmed_departures must be sorted")

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
    unconfirmed_departures: Sequence[datetime] | None = None,
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
        cov = np.array(
            [[to_epoch(a), to_epoch(b)] for a, b in coverage], dtype=np.int64
        )
        cov = cov.reshape(-1, 2)
    unconfirmed = None
    if unconfirmed_departures is not None:
        unconfirmed = np.sort(
            np.array([to_epoch(t) for t in unconfirmed_departures], dtype=np.int64)
        )
    segments = Segments(
        segment_id=np.array([r[0] for r in rows], dtype=str),
        vehicle_id=np.array([r[1] for r in rows], dtype=str),
        t_origin=np.array([r[2] for r in rows], dtype=np.int64),
        t_dest=np.array([r[3] for r in rows], dtype=np.int64),
        coverage=cov,
        unconfirmed_departures=unconfirmed,
    )
    return segments, LoadReport(
        n_rows=n_rows, n_used=len(rows), excluded=dict(excluded)
    )


def load_handoff(directory: str | Path) -> tuple[Segments, LoadReport]:
    """Load one route from D's real-data handoff folder.

    Uses segments.csv for usable runs, stop_events.json for every observed
    departure from the origin stop (any quality) and quality.json for the capture
    window. Each poll gap ({"from": last good poll, "to": next good poll}, written
    by D's exporter when polls are > 1.5 intervals apart) splits the coverage.
    """
    folder = Path(directory)
    route = json.loads((folder / "route.json").read_text(encoding="utf-8"))
    quality = json.loads((folder / "quality.json").read_text(encoding="utf-8"))
    events = json.loads((folder / "stop_events.json").read_text(encoding="utf-8"))
    route_id = route["route_id"]
    if quality["route_id"] != route_id:
        raise ValueError("quality.json and route.json describe different routes")

    def parse(ts: str) -> datetime:
        return datetime.fromisoformat(ts)

    bounds = [parse(quality["capture_start_utc"])]
    for gap in sorted(quality["successful_poll_gaps"], key=lambda g: parse(g["from"])):
        bounds += [parse(gap["from"]), parse(gap["to"])]
    bounds.append(parse(quality["last_poll_utc"]))
    coverage = [(a, b) for a, b in zip(bounds[::2], bounds[1::2], strict=True) if b > a]

    with open(folder / "segments.csv", newline="", encoding="utf-8") as f:
        origin_event_of = {
            r["segment_id"]: r.get("origin_event_id") for r in csv.DictReader(f)
        }
    usable, _ = load_segments_csv(folder / "segments.csv", route_id)
    used_origin_events = {origin_event_of[s] for s in usable.segment_id}

    origin = route["origin"]["naptan_id"]
    pattern = route.get("route_pattern_id")
    unconfirmed = [
        parse(e["inferred_at"])
        for e in events
        if e["naptan_id"] == origin
        and (pattern is None or e.get("route_pattern_id") == pattern)
        and e["event_id"] not in used_origin_events
    ]
    return load_segments_csv(
        folder / "segments.csv",
        route_id,
        coverage=coverage,
        unconfirmed_departures=unconfirmed,
    )


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
        t_origin = np.sort(
            t_origin + np.round(shift * SECONDS_PER_MIN).astype(np.int64)
        )

    ride_s = np.full(len(t_origin), ride_min * SECONDS_PER_MIN)
    if ride_jitter_min > 0:
        ride_s = ride_s + rng.normal(
            0.0, ride_jitter_min * SECONDS_PER_MIN, len(t_origin)
        )
    ride_s = np.maximum(np.round(ride_s), SECONDS_PER_MIN).astype(np.int64)

    n = len(t_origin)
    return Segments(
        segment_id=np.array([f"SYN-{i:05d}" for i in range(n)]),
        vehicle_id=np.array(
            [f"SYN{i % 12:02d}" for i in range(n)]
        ),  # a fleet of 12 buses
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
    are reported, the probability is not. The 90% band is only given for ok rows
    and describes sampling variability among these inferred runs, not calibration.
    """

    depart_at: np.ndarray  # int64
    p_on_time: np.ndarray  # float
    ci_low: np.ndarray  # float, 5th percentile of the run bootstrap (NaN unless ok)
    ci_high: np.ndarray  # float, 95th percentile
    arrive_p50: np.ndarray  # float
    arrive_p90: np.ndarray  # float
    n_trips: np.ndarray  # int, distinct usable runs (segment_id) behind each row
    n_vehicles: np.ndarray  # int, distinct vehicle IDs among those runs
    n_steps: np.ndarray  # int, eligible replay instants
    n_censored: (
        np.ndarray
    )  # int, instants outside coverage or boarding an unconfirmed run
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
    steps = (
        np.arange(-tod_window_min, tod_window_min + 1, dtype=np.int64) * SECONDS_PER_MIN
    )
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
    n_boot: int = N_BOOT,
    seed: int = 0,
) -> Curve:
    """Empirical replay (PLAN.md section 4) for many departures at once.

    For departure d the user reaches O at s = d + walk_to. Each reference instant
    s' boards the first run leaving O at or after s' + board_buffer, giving
    TT(s') = t_D - s' + walk_from and arrival s + TT(s'). An instant is censored
    unless its boarding time and that run's departure lie in the same coverage
    interval, and no unconfirmed departure comes first: the recording edge, capture
    gaps and unpaired buses are unknown, not late.
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

    n_runs = len(segments)
    idx = np.searchsorted(segments.t_origin, board, side="left")
    safe_idx = np.clip(idx, 0, max(n_runs - 1, 0))
    found = idx < n_runs
    if n_runs:
        found &= segments.t_origin[safe_idx] <= cov_end
    valid = in_cov & found

    unconfirmed = segments.unconfirmed_departures
    if len(unconfirmed) and n_runs:
        jb = np.searchsorted(unconfirmed, board, side="left")
        next_unconfirmed = np.where(
            jb < len(unconfirmed),
            unconfirmed[np.clip(jb, 0, len(unconfirmed) - 1)],
            np.inf,
        )
        valid &= ~(next_unconfirmed <= segments.t_origin[safe_idx])

    if n_runs:
        travel = segments.t_dest[safe_idx] - instants + walk_from_s
    else:
        travel = np.zeros_like(instants)
    arrive = np.where(valid, reach[:, None] + travel, np.nan)

    m = len(depart_at)
    n_steps = valid.sum(axis=1)
    _, vehicle_codes = np.unique(segments.vehicle_id, return_inverse=True)
    n_trips = _distinct_per_row(np.where(valid, safe_idx, -1), valid)
    n_vehicles = _distinct_per_row(
        vehicle_codes[safe_idx] if n_runs else safe_idx, valid
    )
    status = evidence_status(n_trips)

    shown = status != "insufficient_data"
    p = np.full(m, np.nan)
    p50 = np.full(m, np.nan)
    p90 = np.full(m, np.nan)
    on_time = valid & (arrive <= deadline)
    if shown.any():
        p[shown] = on_time[shown].sum(axis=1) / n_steps[shown]
        p50[shown], p90[shown] = np.nanpercentile(arrive[shown], [50, 90], axis=1)

    ci_low, ci_high = _run_bootstrap(
        valid, on_time, safe_idx, n_runs, status == "ok", n_boot, seed
    )

    return Curve(
        depart_at=depart_at,
        p_on_time=p,
        ci_low=ci_low,
        ci_high=ci_high,
        arrive_p50=p50,
        arrive_p90=p90,
        n_trips=n_trips,
        n_vehicles=n_vehicles,
        n_steps=n_steps,
        n_censored=instants.shape[1] - n_steps,
        status=status,
    )


def _run_bootstrap(
    valid: np.ndarray,
    on_time: np.ndarray,
    run_idx: np.ndarray,
    n_runs: int,
    rows: np.ndarray,
    n_boot: int,
    seed: int,
) -> tuple[np.ndarray, np.ndarray]:
    """90% band from resampling whole runs, not replay minutes (PLAN.md section 4).

    Poisson(1) weights per run approximate resampling runs with replacement and
    are shared across rows, so the band is consistent along the curve. With
    n_boot=0 no band is computed (e.g. a backtest that only needs p_on_time).
    """
    m = valid.shape[0]
    low = np.full(m, np.nan)
    high = np.full(m, np.nan)
    if n_boot <= 0 or not rows.any() or n_runs == 0:
        return low, high

    sel = np.flatnonzero(rows)
    r, c = np.nonzero(valid[sel])
    flat = r * n_runs + run_idx[sel][r, c]
    size = len(sel) * n_runs
    steps = np.bincount(flat, minlength=size).reshape(len(sel), n_runs)
    hits = np.bincount(flat, weights=on_time[sel][r, c], minlength=size).reshape(
        len(sel), n_runs
    )

    weights = np.random.default_rng(seed).poisson(1.0, size=(n_runs, n_boot))
    denom = steps @ weights
    with np.errstate(invalid="ignore", divide="ignore"):
        boot = np.where(denom > 0, (hits @ weights) / denom, np.nan)
    low[sel], high[sel] = np.nanpercentile(boot, [5, 95], axis=1)
    return low, high


def departure_curve(
    segments: Segments,
    deadline: datetime,
    *,
    walk_to_min: float = 0.0,
    walk_from_min: float = 0.0,
    window_min: int = 90,
    **kwargs,
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
        **kwargs,
    )


MAX_REFERENCE_TRIES = 8


def reference_date_candidates(segments: Segments, deadline: datetime) -> list[date]:
    """Recorded London dates to borrow when the deadline's own date has no trips
    near that time: the same weekday first (most recent week first), then any
    other recorded date (most recent first). The deadline's own date is excluded.
    """
    own = to_epoch(deadline)
    own_date = datetime.fromtimestamp(own, LONDON).date()
    recorded = sorted(
        {datetime.fromtimestamp(int(e), LONDON).date() for e in segments.t_origin},
        reverse=True,
    )
    others = [d for d in recorded if d != own_date]
    same_weekday = [d for d in others if d.weekday() == own_date.weekday()]
    rest = [d for d in others if d.weekday() != own_date.weekday()]
    return (same_weekday + rest)[:MAX_REFERENCE_TRIES]


def departure_curve_with_reference(
    segments: Segments,
    deadline: datetime,
    **kwargs,
) -> tuple[Curve, date | None]:
    """departure_curve on the deadline's own date; if that gives no probability at
    any departure, replay the same London time on the first candidate date that
    does (see reference_date_candidates). Returns the curve and the borrowed date,
    or None when the own date was used or nothing had data.
    """
    curve = departure_curve(segments, deadline, **kwargs)
    if np.isfinite(curve.p_on_time).any():
        return curve, None
    for ref in reference_date_candidates(segments, deadline):
        borrowed = departure_curve(segments, deadline, reference_dates=[ref], **kwargs)
        if np.isfinite(borrowed.p_on_time).any():
            return borrowed, ref
    return curve, None


def p_on_time(
    segments: Segments,
    depart_at: datetime,
    deadline: datetime,
    **kwargs,
) -> float:
    """P(arrive by `deadline` | leave at `depart_at`); NaN under insufficient_data."""
    curve = replay_curve(
        segments, np.array([to_epoch(depart_at)]), to_epoch(deadline), **kwargs
    )
    return float(curve.p_on_time[0])


@dataclass(frozen=True)
class Advice:
    """The advisor's answer (PLAN.md section 4).

    `reason` is "ok", or why there is no recommendation: "too_few_runs" when no
    departure has 15+ runs, or "no_departure_meets_tolerance".
    """

    reason: str
    depart_at: int | None = None
    p_on_time: float | None = None
    conservative_depart_at: int | None = None  # uses the band's lower edge


def recommend(curve: Curve, tolerance: float = DEFAULT_TOLERANCE) -> Advice:
    """Latest departure with empirical P(late) <= tolerance, among ok rows only."""
    ok = curve.status == "ok"
    if not ok.any():
        return Advice(reason="too_few_runs")
    target = 1.0 - tolerance
    meets = ok & (curve.p_on_time >= target)
    if not meets.any():
        return Advice(reason="no_departure_meets_tolerance")
    i = np.flatnonzero(meets)[-1]
    safe = ok & (curve.ci_low >= target)
    conservative = (
        int(curve.depart_at[np.flatnonzero(safe)[-1]]) if safe.any() else None
    )
    return Advice(
        reason="ok",
        depart_at=int(curve.depart_at[i]),
        p_on_time=float(curve.p_on_time[i]),
        conservative_depart_at=conservative,
    )


def what_if(
    curve: Curve, depart_at: int, delays_min: Sequence[int] = (5, 10, 15)
) -> list[tuple[int, float | None, float | None]]:
    """(delay, p_on_time, change) for leaving `delays_min` later; None where unsupported."""
    row = {int(t): i for i, t in enumerate(curve.depart_at)}
    base = row.get(int(depart_at))
    base_p = curve.p_on_time[base] if base is not None else np.nan
    out = []
    for delay in delays_min:
        j = row.get(int(depart_at) + delay * SECONDS_PER_MIN)
        p = curve.p_on_time[j] if j is not None else np.nan
        if np.isnan(p):
            out.append((delay, None, None))
        else:
            out.append(
                (delay, float(p), None if np.isnan(base_p) else float(p - base_p))
            )
    return out
