"""Rolling-origin backtest of M's model (PLAN.md section 4, calibration policy).

At each forecast origin T the model sees only runs that had already arrived by T,
and is scored on departures in [T, T + BLOCK): test blocks are disjoint and always
after their training data. The reference standard is D's inferred stop events,
estimated from TfL predictions, so scores are against inferred events, not measured
arrivals, and never establish validated calibration.
"""

from dataclasses import dataclass

import numpy as np

from app import model
from app.schemas import Calibration, ReliabilityBin

BLOCK_MIN = 30
DEPART_STEP_MIN = 2
# Deadlines relative to the training median ride, so outcomes span likely and unlikely.
DEADLINE_OFFSETS_MIN = (-2, 0, 2, 4, 6, 8, 12)
N_BINS = 5
MIN_RUNS_PRELIMINARY = 15
MIN_BLOCKS_PRELIMINARY = 2
# A wait this many times the usual headway is treated as a capture gap: unknown, not late.
# Placeholder until D supplies recording coverage intervals (tasks/model.md).
SUSPECT_GAP_FACTOR = 4
SECONDS_PER_MIN = 60


@dataclass(frozen=True)
class Outcome:
    p: float
    on_time: bool
    run_id: str
    block: int


def _training_view(segments: model.Segments, t: int) -> model.Segments | None:
    """Runs knowable at time t: every run up to the first one still travelling at t."""
    unfinished = np.nonzero(segments.t_dest >= t)[0]
    k = int(unfinished[0]) if len(unfinished) else len(segments)
    if k < model.LOW_DATA_MIN_RUNS:
        return None
    # Recording counts as complete only until the first unfinished run leaves.
    cov_end = int(segments.t_origin[k]) - 1 if k < len(segments) else t
    return model.Segments(
        segment_id=segments.segment_id[:k],
        vehicle_id=segments.vehicle_id[:k],
        t_origin=segments.t_origin[:k],
        t_dest=segments.t_dest[:k],
        coverage=np.array([[int(segments.t_origin[0]), max(cov_end, int(segments.t_origin[k - 1]))]]),
    )


def backtest(segments: model.Segments) -> tuple[list[Outcome], int]:
    """Scored outcomes, plus how many were censored as suspected capture gaps."""
    n = len(segments)
    censored = 0
    if n < 2 * model.LOW_DATA_MIN_RUNS:
        return [], 0
    block_s = BLOCK_MIN * SECONDS_PER_MIN
    buffer_s = round(model.BOARD_BUFFER_MIN * SECONDS_PER_MIN)
    last_origin = int(segments.t_origin[-1])
    outcomes: list[Outcome] = []
    origin = int(segments.t_origin[0]) + block_s
    block = 0
    while origin + block_s <= last_origin:
        train = _training_view(segments, origin)
        if train is not None:
            median_ride = int(np.median(train.t_dest - train.t_origin))
            headways = np.diff(train.t_origin)
            max_wait = SUSPECT_GAP_FACTOR * float(np.median(headways)) if len(headways) else 0.0
            departs = np.arange(origin, origin + block_s, DEPART_STEP_MIN * SECONDS_PER_MIN)
            # What actually happened: the first recorded run catchable after leaving.
            idx = np.searchsorted(segments.t_origin, departs + buffer_s, side="left")
            for d, i in zip(departs, idx, strict=True):
                if i >= n:
                    continue
                if segments.t_origin[i] - (d + buffer_s) > max_wait:
                    censored += len(DEADLINE_OFFSETS_MIN)
                    continue
                for off in DEADLINE_OFFSETS_MIN:
                    deadline = int(d) + median_ride + off * SECONDS_PER_MIN
                    curve = model.replay_curve(train, np.array([d]), deadline)
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
        origin += block_s
        block += 1
    return outcomes, censored


def summarise(outcomes: list[Outcome], censored: int = 0) -> Calibration:
    gap_note = (
        f" {censored} outcomes were set aside as suspected recording gaps." if censored else ""
    )
    if not outcomes:
        return Calibration(
            bins=[],
            brier_score=None,
            calibration_status="not_validated",
            n_outcomes=0,
            n_runs=0,
            basis="Not enough recorded trips for a held-out backtest yet." + gap_note,
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
            f"Rolling backtest: {n_blocks} held-out {BLOCK_MIN}-min blocks, {n_runs} distinct "
            "later runs, scored against stop events inferred from TfL predictions (not measured "
            "arrivals). Outcomes overlap, so they are not independent samples." + gap_note
        ),
    )
