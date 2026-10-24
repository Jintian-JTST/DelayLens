"""Hand-checked tests for the synthetic timetable and empirical replay.

Reference timetable: a bus leaves O every 10 min on the hour and always takes
exactly 20 min to D. Query times are Europe/London local time; the deadline is
12:00 on Sat 24 Oct 2026 (BST).
"""

import time
from datetime import UTC, date, datetime, timedelta

import numpy as np
import pytest

from app.model import (
    LONDON,
    Segments,
    departure_curve,
    evidence_status,
    load_segments_csv,
    p_on_time,
    reference_instants,
    replay_curve,
    synthetic_segments,
    to_epoch,
)

SAT = date(2026, 10, 24)
START = datetime(2026, 10, 24, 6, tzinfo=LONDON)
END = datetime(2026, 10, 24, 23, tzinfo=LONDON)
DEADLINE = datetime(2026, 10, 24, 12, tzinfo=LONDON)
FIFTEEN_DAYS = [SAT + timedelta(days=k) for k in range(15)]


@pytest.fixture
def timetable() -> Segments:
    """One recorded Saturday, 06:00-23:00 local."""
    return synthetic_segments(START, END, headway_min=10, ride_min=20)


@pytest.fixture
def fortnight() -> Segments:
    """Fifteen recorded days of the same timetable (spans the clock change)."""
    return synthetic_segments(START, END + timedelta(days=14), headway_min=10, ride_min=20)


def at(hh: int, mm: int) -> datetime:
    return datetime(2026, 10, 24, hh, mm, tzinfo=LONDON)


def curve_at(segments: Segments, depart: datetime, deadline: datetime = DEADLINE, **kwargs):
    return replay_curve(segments, np.array([to_epoch(depart)]), to_epoch(deadline), **kwargs)


# --- synthetic generator and inputs -----------------------------------------


def test_regular_timetable_is_exact(timetable: Segments) -> None:
    assert len(timetable) == 17 * 6  # 06:00, 06:10, ..., 22:50
    assert timetable.t_origin[0] == to_epoch(START)
    assert timetable.t_origin[-1] == to_epoch(at(22, 50))
    assert np.all(np.diff(timetable.t_origin) == 600)
    assert np.all(timetable.t_dest - timetable.t_origin == 1200)
    assert timetable.t_origin.dtype == np.int64
    assert len(set(timetable.segment_id)) == len(timetable)
    np.testing.assert_array_equal(timetable.coverage, [[to_epoch(START), to_epoch(END)]])


def test_jitter_is_reproducible_and_valid() -> None:
    kwargs = {"headway_jitter_min": 3, "ride_jitter_min": 5}
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


def test_segments_reject_bad_input() -> None:
    one = {"vehicle_id": np.array(["v1"]), "t_origin": np.array([100])}
    with pytest.raises(ValueError):
        Segments(segment_id=np.array(["s1"]), t_dest=np.array([100]), **one)
    with pytest.raises(ValueError):
        Segments(
            segment_id=np.array(["s1", "s1"]),
            vehicle_id=np.array(["v1", "v2"]),
            t_origin=np.array([100, 200]),
            t_dest=np.array([300, 400]),
        )


def test_evidence_thresholds() -> None:
    assert list(evidence_status([0, 4, 5, 14, 15, 40])) == [
        "insufficient_data",
        "insufficient_data",
        "low_data",
        "low_data",
        "ok",
        "ok",
    ]


def test_load_segments_csv_keeps_only_usable_rows_and_reports_why(tmp_path) -> None:
    route = "bus-24-inbound-warren-leicester"
    header = (
        "segment_id,route_id,vehicle_id,origin_at,destination_at,"
        "travel_seconds,inference_method,quality,source"
    )
    rows = [
        f"b,{route},v2,2026-10-24T17:20:00Z,2026-10-24T17:31:00Z,660,near_stop_prediction,estimated,tfl_live_recording",
        f"a,{route},v1,2026-10-24T17:10:00Z,2026-10-24T17:24:30Z,870,near_stop_prediction,estimated,tfl_live_recording",
        f"a,{route},v1,2026-10-24T17:10:00Z,2026-10-24T17:24:30Z,870,near_stop_prediction,estimated,tfl_live_recording",
        "c,tube-victoria-outbound-brixton-oxford-circus,v3,2026-10-24T17:10:00Z,2026-10-24T17:30:00Z,1200,x,estimated,tfl_live_recording",
        f"d,{route},v4,2026-10-24T17:12:00Z,2026-10-24T17:25:00Z,780,x,uncertain,tfl_live_recording",
        f"e,{route},v5,2026-10-24T17:30:00Z,2026-10-24T17:20:00Z,-600,x,estimated,tfl_live_recording",
        f"f,{route},v6,2026-10-24T17:30:00Z,2026-10-24T17:40:00Z,999,x,estimated,tfl_live_recording",
        f"g,{route},v7,not-a-time,2026-10-24T17:40:00Z,600,x,estimated,tfl_live_recording",
    ]
    path = tmp_path / "segments.csv"
    path.write_text("\n".join([header, *rows]) + "\n", encoding="utf-8")

    segments, report = load_segments_csv(path, route)
    assert list(segments.segment_id) == ["a", "b"]  # sorted by origin time
    assert segments.t_dest[0] - segments.t_origin[0] == 870
    assert report.n_rows == 8 and report.n_used == 2
    assert report.excluded == {
        "duplicate_segment_id": 1,
        "other_route": 1,
        "not_estimated": 1,
        "non_positive_duration": 1,
        "duration_mismatch": 1,
        "bad_timestamp": 1,
    }


# --- empirical replay: hand-checked curves -----------------------------------


def test_exact_time_of_day_gives_step_curve(fortnight: Segments) -> None:
    # Reach O at d; board the first bus at or after d + 1 min; ride 20 min. The
    # 11:40 bus arrives at 12:00 exactly (on time), so 11:39 is the last safe
    # departure; at 11:40 you need the 11:50 bus and arrive at 12:10. Replaying the
    # same local time on 15 explicitly chosen dates gives 15 runs: status ok.
    exact = {"tod_window_min": 0, "reference_dates": FIFTEEN_DAYS}
    for minute in range(20, 40):
        assert p_on_time(fortnight, at(11, minute), DEADLINE, **exact) == 1.0
    for minute in range(40, 51):
        assert p_on_time(fortnight, at(11, minute), DEADLINE, **exact) == 0.0
    curve = curve_at(fortnight, at(11, 39), **exact)
    assert curve.n_trips[0] == 15 and curve.status[0] == "ok"


def test_time_of_day_window_gives_ramp(timetable: Segments) -> None:
    # +/- 30 min at 1-min steps = 61 replay instants covering every phase of the
    # 10-min cycle. An instant phi min after a departure waits 10 - phi min, so
    # the travel time is 21..30 min.
    # 11:30 -> 30 min to spare: every instant is on time.
    assert p_on_time(timetable, at(11, 30), DEADLINE) == 1.0
    # 11:35 -> 25 min to spare: need a wait <= 5, i.e. phi in 5..9. The instants
    # 11:05..12:05 contain each phase 6 times, plus one extra phase 5 (12:05):
    # 5 * 6 + 1 = 31 of 61.
    assert p_on_time(timetable, at(11, 35), DEADLINE) == pytest.approx(31 / 61)
    # 11:40 -> 20 min to spare: the 20-min ride alone uses it all; never on time.
    assert p_on_time(timetable, at(11, 40), DEADLINE) == 0.0


def test_walking_time_shifts_the_step(fortnight: Segments) -> None:
    # A 4-min walk from D means the bus must arrive by 11:56: the 11:30 bus. You
    # catch it only if you reach O by 11:29, so with a 6-min walk to O, leave by
    # 11:23. Leaving at 11:24 means the 11:40 bus and arriving at 12:04.
    kwargs = {"walk_to_min": 6, "walk_from_min": 4, "tod_window_min": 0, "reference_dates": FIFTEEN_DAYS}
    assert p_on_time(fortnight, at(11, 23), DEADLINE, **kwargs) == 1.0
    assert p_on_time(fortnight, at(11, 24), DEADLINE, **kwargs) == 0.0


def test_arrivals_and_distinct_runs(timetable: Segments) -> None:
    # +/- 30 min around 11:30: boarding from 11:01..12:01 uses the buses
    # 11:10, 11:20, ..., 12:10, which is 7 distinct runs (not 61 instants):
    # low_data, so a descriptive probability is shown.
    curve = curve_at(timetable, at(11, 30))
    assert curve.n_trips[0] == 7
    assert curve.n_steps[0] == 61 and curve.n_censored[0] == 0
    assert curve.n_vehicles[0] == 7
    assert curve.status[0] == "low_data"
    # Travel times are 21..30 min, so arrivals spread over 11:51..12:00.
    assert to_epoch(at(11, 51)) <= curve.arrive_p50[0] <= curve.arrive_p90[0]
    assert curve.arrive_p90[0] <= to_epoch(DEADLINE)


def test_too_few_runs_gives_counts_but_no_probability(timetable: Segments) -> None:
    # Exact time of day on one date is a single run: insufficient_data.
    curve = curve_at(timetable, at(11, 35), tod_window_min=0)
    assert curve.n_trips[0] == 1
    assert curve.status[0] == "insufficient_data"
    assert np.isnan(curve.p_on_time[0]) and np.isnan(curve.arrive_p50[0])


# --- empirical replay: dates, clock change and censoring ----------------------


def test_dates_are_not_pooled_unless_requested() -> None:
    two_days = synthetic_segments(START, END + timedelta(days=1))
    default = curve_at(two_days, at(11, 30))
    pooled = curve_at(two_days, at(11, 30), reference_dates=[SAT, SAT + timedelta(days=1)])
    assert default.n_trips[0] == 7
    assert pooled.n_trips[0] == 14


def test_repeated_local_hour_stays_distinct() -> None:
    # 01:30 happens twice on Sun 25 Oct: 00:30 UTC (BST) then 01:30 UTC (GMT).
    first = datetime(2026, 10, 25, 0, 30, tzinfo=UTC)
    second = datetime(2026, 10, 25, 1, 30, tzinfo=UTC)
    sun = [date(2026, 10, 25)]
    reach = np.array([to_epoch(first), to_epoch(second)])
    inst = reference_instants(reach, sun, tod_window_min=0)
    np.testing.assert_array_equal(inst[:, 0], reach)
    # The same local 12:00 maps to 11:00 UTC on Saturday and 12:00 UTC on Sunday.
    noon = reference_instants(np.array([to_epoch(DEADLINE)]), [SAT, sun[0]], tod_window_min=0)
    assert noon[0, 1] - noon[0, 0] == 86_400 + 3_600


def test_capture_gap_is_censored_not_late(timetable: Segments) -> None:
    # Recording dropped 11:35-11:55, losing the 11:40 and 11:50 buses.
    keep = (timetable.t_origin < to_epoch(at(11, 35))) | (timetable.t_origin > to_epoch(at(11, 55)))
    gappy = Segments(
        segment_id=timetable.segment_id[keep],
        vehicle_id=timetable.vehicle_id[keep],
        t_origin=timetable.t_origin[keep],
        t_dest=timetable.t_dest[keep],
        coverage=np.array(
            [[to_epoch(START), to_epoch(at(11, 35))], [to_epoch(at(11, 55)), to_epoch(END)]]
        ),
    )
    # Leaving 11:30, instants 11:00..12:00 board at 11:01..12:01.
    # Eligible: boards 11:01..11:30 (next bus 11:10/11:20/11:30, 30 instants) and
    # 11:55..12:01 (12:00/12:10 buses, 7 instants). Censored: boards 11:31..11:35,
    # whose next observed bus is after the gap, and 11:36..11:54 inside it: 24.
    curve = curve_at(gappy, at(11, 30))
    assert curve.n_steps[0] == 37 and curve.n_censored[0] == 24
    assert curve.n_trips[0] == 5  # 11:10, 11:20, 11:30, 12:00, 12:10
    # Every eligible instant waits <= 10 min, so all 37 are on time. Treating the
    # gap as "no bus until 12:00" would add waits of up to 30 min (41/61).
    assert curve.p_on_time[0] == 1.0


def test_end_of_recording_is_censored(timetable: Segments) -> None:
    # The last bus leaves 22:50 and recording stops at 23:00: leaving 22:55 has
    # nothing observed to catch, which is unknown rather than late.
    late = datetime(2026, 10, 24, 23, 30, tzinfo=LONDON)
    curve = curve_at(timetable, at(22, 55), late, tod_window_min=0)
    assert curve.n_steps[0] == 0 and curve.n_censored[0] == 1
    assert curve.status[0] == "insufficient_data"
    assert np.isnan(p_on_time(timetable, at(22, 55), late, tod_window_min=0))


# --- curve shape and performance --------------------------------------------


def test_departure_curve_covers_window_and_is_monotone(fortnight: Segments) -> None:
    curve = departure_curve(
        fortnight, DEADLINE, walk_to_min=6, walk_from_min=4, reference_dates=FIFTEEN_DAYS
    )
    assert len(curve.depart_at) == 91  # T - 90 .. T at 1-min steps
    assert curve.depart_at[0] == to_epoch(DEADLINE) - 90 * 60
    assert curve.depart_at[-1] == to_epoch(DEADLINE)
    assert np.all(curve.status == "ok")
    # Leaving later can never make you more likely to be on time.
    assert np.all(np.diff(curve.p_on_time) <= 1e-12)


def test_curve_is_fast_on_a_weekend_of_noisy_data() -> None:
    weekend = synthetic_segments(
        START, END + timedelta(days=1), headway_min=4, headway_jitter_min=2, ride_jitter_min=6
    )
    dates = [SAT, SAT + timedelta(days=1)]
    departure_curve(weekend, DEADLINE, reference_dates=dates)  # warm-up
    t0 = time.perf_counter()
    curve = departure_curve(
        weekend, DEADLINE, walk_to_min=5, walk_from_min=5, reference_dates=dates
    )
    elapsed_ms = (time.perf_counter() - t0) * 1000
    assert elapsed_ms < 50, f"{elapsed_ms:.1f} ms"
    assert not np.isnan(curve.p_on_time).any()
    assert np.all((curve.p_on_time >= 0) & (curve.p_on_time <= 1))
