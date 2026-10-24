"""Hand-checked tests for the synthetic timetable and empirical replay.

Reference timetable: a bus leaves O every 10 min on the hour (06:00-23:00 UTC,
Sat 24 Oct 2026) and always takes exactly 20 min to D. Deadline 12:00 UTC.
"""

from datetime import datetime, timedelta, timezone

import numpy as np
import pytest

from app.model import Segments, p_on_time, synthetic_segments, to_epoch

DAY = datetime(2026, 10, 24, tzinfo=timezone.utc)
START = DAY.replace(hour=6)
END = DAY.replace(hour=23)
DEADLINE = DAY.replace(hour=12)


@pytest.fixture
def timetable() -> Segments:
    return synthetic_segments(START, END, headway_min=10, ride_min=20)


def at(hh: int, mm: int) -> datetime:
    return DAY.replace(hour=hh, minute=mm)


# --- synthetic generator ---------------------------------------------------


def test_regular_timetable_is_exact(timetable: Segments) -> None:
    assert len(timetable) == 17 * 6  # 06:00, 06:10, ..., 22:50
    assert timetable.t_origin[0] == to_epoch(START)
    assert timetable.t_origin[-1] == to_epoch(at(22, 50))
    assert np.all(np.diff(timetable.t_origin) == 600)
    assert np.all(timetable.t_dest - timetable.t_origin == 1200)
    assert timetable.t_origin.dtype == np.int64
    assert len(set(timetable.vehicle_id)) == len(timetable)


def test_jitter_is_reproducible_and_valid() -> None:
    kwargs = dict(headway_jitter_min=3, ride_jitter_min=5)
    a = synthetic_segments(START, END, seed=1, **kwargs)
    b = synthetic_segments(START, END, seed=1, **kwargs)
    c = synthetic_segments(START, END, seed=2, **kwargs)
    np.testing.assert_array_equal(a.t_dest, b.t_dest)
    assert not np.array_equal(a.t_dest, c.t_dest)
    assert np.all(np.diff(a.t_origin) >= 0)
    assert np.all(a.t_dest - a.t_origin >= 60)


def test_naive_datetimes_are_rejected() -> None:
    with pytest.raises(ValueError):
        synthetic_segments(datetime(2026, 10, 24, 6), datetime(2026, 10, 24, 23))


def test_segments_reject_non_positive_rides() -> None:
    with pytest.raises(ValueError):
        Segments(np.array(["v1"]), np.array([100]), np.array([100]))


def test_utc_has_no_repeated_hour_across_clock_change() -> None:
    # 00:00-03:00 UTC Sun 25 Oct spans the BST -> GMT change at 01:00 UTC.
    sun = datetime(2026, 10, 25, tzinfo=timezone.utc)
    trips = synthetic_segments(sun, sun + timedelta(hours=3))
    assert len(trips) == 18
    assert np.all(np.diff(trips.t_origin) == 600)


# --- empirical replay (implemented in the next task) -----------------------

replay_pending = pytest.mark.xfail(
    raises=NotImplementedError, strict=True, reason="replay lands Sat 15:00-16:30"
)


@replay_pending
def test_exact_time_of_day_gives_step_curve(timetable: Segments) -> None:
    # Reach the stop at d; the first bus at or after d + 1 min arrives 20 min later.
    # The 11:40 bus arrives at 12:00 exactly (on time), so leaving at 11:39 is the
    # last safe departure; at 11:40 you need the 11:50 bus and arrive 12:10.
    for minute in range(20, 40):
        assert p_on_time(timetable, at(11, minute), DEADLINE, tod_window_min=0) == 1.0
    for minute in range(40, 51):
        assert p_on_time(timetable, at(11, minute), DEADLINE, tod_window_min=0) == 0.0


@replay_pending
def test_time_of_day_window_gives_ramp(timetable: Segments) -> None:
    # +/- 30 min at 1-min steps = 61 replay instants covering every phase of the
    # 10-min cycle. An instant phi min after a departure waits 10 - phi min, so the
    # travel time is 21..30 min.
    # 11:30 -> 30 min to spare: every instant is on time.
    assert p_on_time(timetable, at(11, 30), DEADLINE) == 1.0
    # 11:35 -> 25 min to spare: need a wait <= 5, i.e. phi in 5..9. The instants
    # 11:05..12:05 contain each phase 6 times, plus one extra phase 5 (12:05):
    # 5 * 6 + 1 = 31 of 61.
    assert p_on_time(timetable, at(11, 35), DEADLINE) == pytest.approx(31 / 61)
    # 11:40 -> 20 min to spare: the 20-min ride alone uses it all; never on time.
    assert p_on_time(timetable, at(11, 40), DEADLINE) == 0.0


@replay_pending
def test_walking_time_shifts_the_step(timetable: Segments) -> None:
    # A 4-min walk from D means the bus must arrive by 11:56: the 11:30 bus. You
    # catch it only if you reach O by 11:29, so with a 6-min walk to O, leave by
    # 11:23. Leaving at 11:24 means the 11:40 bus and arriving at 12:04.
    kwargs = dict(walk_to_min=6, walk_from_min=4, tod_window_min=0)
    assert p_on_time(timetable, at(11, 23), DEADLINE, **kwargs) == 1.0
    assert p_on_time(timetable, at(11, 24), DEADLINE, **kwargs) == 0.0
