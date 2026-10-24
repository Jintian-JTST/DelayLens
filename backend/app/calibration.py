"""Blocked hold-out backtest of M's model (PLAN.md section 4, calibration policy).

The recording is cut into 30-min blocks. Each block is held out in turn: the
model sees every run, unconfirmed departure and coverage outside it (both sides,
so bus headways still give it enough runs), and is scored on departures inside
it. A departure is scored only when its outcome is known from a run inside the
block: outcomes that fall in a recording gap, behind an unconfirmed bus, or on a
run after the block (which the model may have seen) are set aside. The reference
standard is D's inferred stop events, estimated from TfL predictions, so scores
are against inferred events, not measured arrivals, and never establish validated
calibration.
"""

from dataclasses import dataclass

import numpy as np

from app import curves, model
from app.schemas import Calibration, ReliabilityBin

BLOCK_MIN = 30
DEPART_STEP_MIN = 2
# Deadlines relative to the training median ride, wide enough to cover bus waits.
DEADLINE_OFFSETS_MIN = (-2, 0, 2, 4, 6, 8, 12, 16)
N_BINS = 5
MIN_RUNS_PRELIMINARY = 15
MIN_BLOCKS_PRELIMINARY = 2
SECONDS_PER_MIN = 60


@dataclass(frozen=True)
class Outcome:
    p: float
    on_time: bool
    run_id: str
    block: int


def _without(cov: np.ndarray, a: int, b: int) -> np.ndarray:
    """Coverage intervals with [a, b) removed."""
    out = []
    for start, end in cov:
        if end < a or start >= b:
            out.append((start, end))
            continue
        if start < a:
            out.append((start, a - 1))
        if end >= b:
            out.append((b, end))
    return np.array(out, dtype=np.int64).reshape(-1, 2)


def _held_out_training(segments: model.Segments, a: int, b: int) -> model.Segments | None:
    keep = (segments.t_origin < a) | (segments.t_origin >= b)
    if int(keep.sum()) < model.LOW_DATA_MIN_RUNS:
        return None
    unconf = segments.unconfirmed_departures
    return model.Segments(
        segment_id=segments.segment_id[keep],
        vehicle_id=segments.vehicle_id[keep],
        t_origin=segments.t_origin[keep],
        t_dest=segments.t_dest[keep],
        coverage=_without(segments.coverage, a, b),
        unconfirmed_departures=unconf[(unconf < a) | (unconf >= b)],
    )


def _known_outcome(segments: model.Segments, board: int, b: int) -> int | None:
    """Index of the run actually caught after `board`, if that is knowable in-block."""
    cov = segments.coverage
    ci = int(np.searchsorted(cov[:, 0], board, side="right")) - 1
    if ci < 0 or board > cov[ci, 1]:
        return None  # left during a recording gap
    i = int(np.searchsorted(segments.t_origin, board, side="left"))
    if i >= len(segments) or segments.t_origin[i] > cov[ci, 1] or segments.t_origin[i] >= b:
        return None  # next run is in a gap or after the held-out block
    unconf = segments.unconfirmed_departures
    j = int(np.searchsorted(unconf, board, side="left"))
    if j < len(unconf) and unconf[j] <= segments.t_origin[i]:
        return None  # an unconfirmed bus came first: the outcome is unknown
    return i


def backtest(segments: model.Segments) -> tuple[list[Outcome], int]:
    """Scored outcomes, plus how many were set aside as unknowable."""
    if len(segments) < 2 * model.LOW_DATA_MIN_RUNS:
        return [], 0
    block_s = BLOCK_MIN * SECONDS_PER_MIN
    buffer_s = round(model.BOARD_BUFFER_MIN * SECONDS_PER_MIN)
    start, end = int(segments.coverage[0, 0]), int(segments.coverage[-1, 1])
    outcomes: list[Outcome] = []
    set_aside = 0
    for block, a in enumerate(range(start, end - block_s + 1, block_s)):
        b = a + block_s
        train = _held_out_training(segments, a, b)
        if train is None:
            continue
        median_ride = int(np.median(train.t_dest - train.t_origin))
        for d in range(a, b, DEPART_STEP_MIN * SECONDS_PER_MIN):
            i = _known_outcome(segments, d + buffer_s, b)
            if i is None:
                set_aside += len(DEADLINE_OFFSETS_MIN)
                continue
            for off in DEADLINE_OFFSETS_MIN:
                deadline = d + median_ride + off * SECONDS_PER_MIN
                curve = model.replay_curve(
                    train,
                    np.array([d]),
                    deadline,
                    tod_window_min=curves.TOD_WINDOW_MIN,
                    n_boot=0,  # the backtest scores p_on_time only; skip the unused band
                )
                p = float(curve.p_on_time[0])
                if np.isnan(p):
                    continue  # insufficient_data: the model made no prediction
                outcomes.append(
                    Outcome(
                        p=p,
                        on_time=bool(segments.t_dest[i] <= deadline),
                        run_id=str(segments.segment_id[i]),
                        block=block,
                    )
                )
    return outcomes, set_aside


def summarise(outcomes: list[Outcome], set_aside: int = 0) -> Calibration:
    note = (
        f" {set_aside} outcomes were set aside as unknowable (recording gaps, "
        "unconfirmed buses, or runs outside the held-out block)."
        if set_aside
        else ""
    )
    if not outcomes:
        return Calibration(
            bins=[],
            brier_score=None,
            calibration_status="not_validated",
            n_outcomes=0,
            n_runs=0,
            basis="Not enough recorded trips for a held-out backtest yet." + note,
        )
    p = np.array([o.p for o in outcomes])
    y = np.array([o.on_time for o in outcomes], dtype=float)
    which = np.minimum((p * N_BINS).astype(int), N_BINS - 1)
    bins = [
        ReliabilityBin(
            predicted=round(float(p[which == b].mean()), 4),
            observed=round(float(y[which == b].mean()), 4),
            n=int((which == b).sum()),
        )
        for b in range(N_BINS)
        if (which == b).any()
    ]
    n_runs = len({o.run_id for o in outcomes})
    n_blocks = len({o.block for o in outcomes})
    preliminary = n_runs >= MIN_RUNS_PRELIMINARY and n_blocks >= MIN_BLOCKS_PRELIMINARY
    return Calibration(
        bins=bins,
        brier_score=round(float(np.mean((p - y) ** 2)), 4),
        calibration_status="preliminary" if preliminary else "not_validated",
        n_outcomes=len(outcomes),
        n_runs=n_runs,
        basis=(
            f"Blocked hold-out: {n_blocks} held-out {BLOCK_MIN}-min blocks, {n_runs} distinct "
            "runs, each scored by a model trained on the other blocks. Scored against stop "
            "events inferred from TfL predictions (not measured arrivals). Outcomes overlap, "
            "so they are not independent samples." + note
        ),
    )
