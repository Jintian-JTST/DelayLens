"""Hand-checked tests for the synthetic timetable and empirical replay.

Reference timetable: a bus leaves O every 10 min on the hour and always takes
exactly 20 min to D. Query times are Europe/London local time; the deadline is
12:00 on Sat 24 Oct 2026 (BST).
"""

import json
import time
from datetime import UTC, date, datetime, timedelta

import numpy as np
import pytest

from app.model import (
    LONDON,
    Segments,
    departure_curve,
    departure_curve_with_reference,
    evidence_status,
    load_handoff,
    load_segments_csv,
    p_on_time,
    recommend,
    reference_date_candidates,
    reference_instants,
    replay_curve,
    replay_transfer_curve,
    synthetic_segments,
    to_epoch,
    transfer_curve_with_reference,
    what_if,
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
    return synthetic_segments(
        START, END + timedelta(days=14), headway_min=10, ride_min=20
    )


def at(hh: int, mm: int) -> datetime:
    return datetime(2026, 10, 24, hh, mm, tzinfo=LONDON)


def curve_at(
    segments: Segments, depart: datetime, deadline: datetime = DEADLINE, **kwargs
):
    return replay_curve(
        segments, np.array([to_epoch(depart)]), to_epoch(deadline), **kwargs
    )


# --- synthetic generator and inputs -----------------------------------------


def test_regular_timetable_is_exact(timetable: Segments) -> None:
    assert len(timetable) == 17 * 6  # 06:00, 06:10, ..., 22:50
    assert timetable.t_origin[0] == to_epoch(START)
    assert timetable.t_origin[-1] == to_epoch(at(22, 50))
    assert np.all(np.diff(timetable.t_origin) == 600)
    assert np.all(timetable.t_dest - timetable.t_origin == 1200)
    assert timetable.t_origin.dtype == np.int64
    assert len(set(timetable.segment_id)) == len(timetable)
    np.testing.assert_array_equal(
        timetable.coverage, [[to_epoch(START), to_epoch(END)]]
    )


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
    kwargs = {
        "walk_to_min": 6,
        "walk_from_min": 4,
        "tod_window_min": 0,
        "reference_dates": FIFTEEN_DAYS,
    }
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
    pooled = curve_at(
        two_days, at(11, 30), reference_dates=[SAT, SAT + timedelta(days=1)]
    )
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
    noon = reference_instants(
        np.array([to_epoch(DEADLINE)]), [SAT, sun[0]], tod_window_min=0
    )
    assert noon[0, 1] - noon[0, 0] == 86_400 + 3_600


def test_capture_gap_is_censored_not_late(timetable: Segments) -> None:
    # Recording dropped 11:35-11:55, losing the 11:40 and 11:50 buses.
    keep = (timetable.t_origin < to_epoch(at(11, 35))) | (
        timetable.t_origin > to_epoch(at(11, 55))
    )
    gappy = Segments(
        segment_id=timetable.segment_id[keep],
        vehicle_id=timetable.vehicle_id[keep],
        t_origin=timetable.t_origin[keep],
        t_dest=timetable.t_dest[keep],
        coverage=np.array(
            [
                [to_epoch(START), to_epoch(at(11, 35))],
                [to_epoch(at(11, 55)), to_epoch(END)],
            ]
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
        fortnight,
        DEADLINE,
        walk_to_min=6,
        walk_from_min=4,
        reference_dates=FIFTEEN_DAYS,
    )
    assert len(curve.depart_at) == 91  # T - 90 .. T at 1-min steps
    assert curve.depart_at[0] == to_epoch(DEADLINE) - 90 * 60
    assert curve.depart_at[-1] == to_epoch(DEADLINE)
    assert np.all(curve.status == "ok")
    # Leaving later can never make you more likely to be on time.
    assert np.all(np.diff(curve.p_on_time) <= 1e-12)


def test_curve_is_fast_on_a_weekend_of_noisy_data() -> None:
    weekend = synthetic_segments(
        START,
        END + timedelta(days=1),
        headway_min=4,
        headway_jitter_min=2,
        ride_jitter_min=6,
    )
    dates = [SAT, SAT + timedelta(days=1)]
    departure_curve(weekend, DEADLINE, reference_dates=dates)  # warm-up
    # Regression guard, not the benchmark: PLAN's < 50 ms target is measured
    # separately (about 8.5 ms on an M-series Mac). Best of 5 so a busy laptop
    # (e.g. recorders running) does not fail the suite.
    timings = []
    for _ in range(5):
        t0 = time.perf_counter()
        curve = departure_curve(
            weekend, DEADLINE, walk_to_min=5, walk_from_min=5, reference_dates=dates
        )
        timings.append((time.perf_counter() - t0) * 1000)
    assert min(timings) < 250, f"best of 5: {min(timings):.1f} ms"
    assert not np.isnan(curve.p_on_time).any()
    assert np.all((curve.p_on_time >= 0) & (curve.p_on_time <= 1))


# --- unconfirmed departures, band, advisor and what-if -------------------------


def test_unconfirmed_departure_is_censored_not_skipped(timetable: Segments) -> None:
    # The 11:40 bus left O but has no usable segment (e.g. its D event was uncertain).
    bus = timetable.t_origin == to_epoch(at(11, 40))
    keep = ~bus
    partial = Segments(
        segment_id=timetable.segment_id[keep],
        vehicle_id=timetable.vehicle_id[keep],
        t_origin=timetable.t_origin[keep],
        t_dest=timetable.t_dest[keep],
        coverage=timetable.coverage,
        unconfirmed_departures=timetable.t_origin[bus],
    )
    # Leaving 11:30, boards 11:31..11:40 (10 instants) would catch the 11:40 bus:
    # censored. Skipping to the 11:50 bus instead would invent waits of up to 19 min.
    curve = curve_at(partial, at(11, 30))
    assert curve.n_censored[0] == 10 and curve.n_steps[0] == 51
    assert curve.n_trips[0] == 6  # 11:10, 11:20, 11:30, 11:50, 12:00, 12:10
    assert curve.p_on_time[0] == 1.0


def test_band_only_for_ok_rows_and_brackets_estimate() -> None:
    noisy = synthetic_segments(
        START,
        END + timedelta(days=14),
        headway_min=8,
        headway_jitter_min=3,
        ride_jitter_min=6,
    )
    curve = departure_curve(
        noisy, DEADLINE, walk_to_min=5, walk_from_min=5, reference_dates=FIFTEEN_DAYS
    )
    ok = curve.status == "ok"
    assert ok.all()
    assert np.all(curve.ci_low <= curve.p_on_time + 1e-12)
    assert np.all(curve.p_on_time <= curve.ci_high + 1e-12)
    assert np.any(curve.ci_high - curve.ci_low > 0)  # noisy data: a real band
    again = departure_curve(
        noisy, DEADLINE, walk_to_min=5, walk_from_min=5, reference_dates=FIFTEEN_DAYS
    )
    np.testing.assert_array_equal(curve.ci_low, again.ci_low)  # reproducible
    low = curve_at(synthetic_segments(START, END), at(11, 30))  # 7 runs: low_data
    assert low.status[0] == "low_data" and np.isnan(low.ci_low[0])


def test_advisor_picks_latest_safe_departure(fortnight: Segments) -> None:
    curve = departure_curve(
        fortnight, DEADLINE, tod_window_min=0, reference_dates=FIFTEEN_DAYS
    )
    advice = recommend(curve, tolerance=0.10)
    # Hand-checked step: 11:39 is the last departure that is always on time.
    assert advice.reason == "ok"
    assert advice.depart_at == to_epoch(at(11, 39))
    assert advice.p_on_time == 1.0
    assert advice.conservative_depart_at == to_epoch(at(11, 39))  # no spread: same


def test_advisor_suppressed_below_fifteen_runs(timetable: Segments) -> None:
    curve = departure_curve(timetable, DEADLINE)  # one date, about 7 runs per row
    assert not np.any(curve.status == "ok")
    advice = recommend(curve)
    assert advice.reason == "too_few_runs" and advice.depart_at is None


def test_advisor_reports_when_nothing_meets_tolerance(fortnight: Segments) -> None:
    # Only 11:50..12:00 departures: the 20-min ride makes every one late.
    curve = departure_curve(
        fortnight,
        DEADLINE,
        window_min=10,
        tod_window_min=0,
        reference_dates=FIFTEEN_DAYS,
    )
    assert recommend(curve).reason == "no_departure_meets_tolerance"


def test_what_if_reads_the_curve(fortnight: Segments) -> None:
    curve = departure_curve(
        fortnight, DEADLINE, tod_window_min=0, reference_dates=FIFTEEN_DAYS
    )
    result = what_if(curve, to_epoch(at(11, 35)))
    # 11:35 is safe; leaving 5, 10 or 15 min later (11:40..11:50) always misses.
    assert result == [(5, 0.0, -1.0), (10, 0.0, -1.0), (15, 0.0, -1.0)]
    # 11:50 + 15 min = 12:05 is outside the curve: unavailable, not zero.
    assert what_if(curve, to_epoch(at(11, 50)))[-1] == (15, None, None)


# --- D's handoff folder --------------------------------------------------------


def _write_handoff(folder, *, gaps=()) -> None:
    route = {
        "route_id": "bus-24-inbound-warren-leicester",
        "route_pattern_id": "24-inbound-branch-0",
        "origin": {"naptan_id": "O1"},
        "destination": {"naptan_id": "D1"},
    }
    quality = {
        "route_id": route["route_id"],
        "capture_start_utc": "2026-10-24T13:53:05.672238Z",
        "last_poll_utc": "2026-10-24T14:23:35.721234Z",
        "successful_poll_gaps": list(gaps),
        "missing_successful_slot_starts_utc": [],
    }

    def event(eid, stop, ts, quality="estimated"):
        return {
            "event_id": eid,
            "route_pattern_id": "24-inbound-branch-0",
            "naptan_id": stop,
            "inferred_at": ts,
            "quality": quality,
        }

    events = [
        event("e1", "O1", "2026-10-24T13:56:07.000000Z"),
        event("e2", "D1", "2026-10-24T14:12:53.000000Z"),
        event("e3", "O1", "2026-10-24T14:01:00.000000Z", "uncertain"),
        event("e4", "O1", "2026-10-24T14:07:51.000000Z"),
        event("e5", "D1", "2026-10-24T14:21:43.000000Z"),
    ]
    csv_rows = [
        (
            "segment_id,route_id,vehicle_id,origin_at,destination_at,travel_seconds,"
            "inference_method,quality,source,origin_event_id,destination_event_id"
        ),
        (
            f"s1,{route['route_id']},V1,2026-10-24T13:56:07.000000Z,2026-10-24T14:12:53.000000Z,"
            "1006.0,near_stop_prediction_v1,estimated,tfl_live_recording,e1,e2"
        ),
        (
            f"s2,{route['route_id']},V2,2026-10-24T14:07:51.000000Z,2026-10-24T14:21:43.000000Z,"
            "832.0,near_stop_prediction_v1,estimated,tfl_live_recording,e4,e5"
        ),
    ]
    (folder / "route.json").write_text(json.dumps(route), encoding="utf-8")
    (folder / "quality.json").write_text(json.dumps(quality), encoding="utf-8")
    (folder / "stop_events.json").write_text(json.dumps(events), encoding="utf-8")
    (folder / "segments.csv").write_text("\n".join(csv_rows) + "\n", encoding="utf-8")


def test_load_handoff_uses_capture_window_and_unpaired_departures(tmp_path) -> None:
    _write_handoff(tmp_path)
    segments, report = load_handoff(tmp_path)
    assert report.n_used == 2
    assert list(segments.segment_id) == ["s1", "s2"]
    # The uncertain 14:01 departure from O is kept as an unconfirmed departure.
    np.testing.assert_array_equal(
        segments.unconfirmed_departures,
        [to_epoch(datetime(2026, 10, 24, 14, 1, tzinfo=UTC))],
    )
    start = datetime(2026, 10, 24, 13, 53, 5, 672238, tzinfo=UTC)
    assert segments.coverage[0, 0] == to_epoch(start)


def test_load_handoff_splits_coverage_at_poll_gaps(tmp_path) -> None:
    # D's exporter format: last good poll before the gap, first good poll after.
    gap = {
        "from": "2026-10-24T14:00:00Z",
        "to": "2026-10-24T14:05:00Z",
        "seconds": 300.0,
    }
    _write_handoff(tmp_path, gaps=[gap])
    segments, _ = load_handoff(tmp_path)

    def utc(hh, mm):
        return to_epoch(datetime(2026, 10, 24, hh, mm, tzinfo=UTC))

    assert segments.coverage.shape == (2, 2)
    assert segments.coverage[0, 1] == utc(14, 0)
    assert segments.coverage[1, 0] == utc(14, 5)


def test_n_boot_zero_skips_the_band_but_keeps_the_estimate(fortnight: Segments) -> None:
    kwargs = {"tod_window_min": 0, "reference_dates": FIFTEEN_DAYS}
    with_band = curve_at(fortnight, at(11, 39), **kwargs)
    no_band = curve_at(fortnight, at(11, 39), n_boot=0, **kwargs)
    assert no_band.status[0] == "ok"
    assert no_band.p_on_time[0] == with_band.p_on_time[0]
    assert np.isnan(no_band.ci_low[0]) and np.isnan(no_band.ci_high[0])


# --- borrowing a recorded day when the deadline's date has none --------------


def test_own_date_is_used_when_it_has_trips(timetable: Segments) -> None:
    curve, ref = departure_curve_with_reference(timetable, DEADLINE, window_min=30)
    assert ref is None
    assert np.isfinite(curve.p_on_time).all()


def test_unrecorded_day_replays_the_most_recent_day(timetable: Segments) -> None:
    sunday = datetime(2026, 10, 25, 12, tzinfo=LONDON)  # after the clock change
    plain = departure_curve(timetable, sunday, window_min=30)
    assert not np.isfinite(plain.p_on_time).any()

    curve, ref = departure_curve_with_reference(timetable, sunday, window_min=30)
    assert ref == SAT
    expected = departure_curve(timetable, sunday, window_min=30, reference_dates=[SAT])
    np.testing.assert_array_equal(curve.p_on_time, expected.p_on_time)
    np.testing.assert_array_equal(curve.n_trips, expected.n_trips)
    # Same London clock time as Saturday, so arrivals shift by the 25-hour day
    # between 12:00 BST Saturday and 12:00 GMT Sunday.
    saturday = departure_curve(timetable, DEADLINE, window_min=30)
    shift = to_epoch(sunday) - to_epoch(DEADLINE)
    assert shift == 25 * 3600
    np.testing.assert_array_equal(curve.p_on_time, saturday.p_on_time)
    np.testing.assert_array_equal(curve.arrive_p50, saturday.arrive_p50 + shift)


def test_same_weekday_is_preferred_over_a_more_recent_day() -> None:
    fri = date(2026, 10, 23)
    two_days = synthetic_segments(
        datetime(2026, 10, 23, 6, tzinfo=LONDON), END, headway_min=10, ride_min=20
    )
    next_friday = datetime(2026, 10, 30, 12, tzinfo=LONDON)
    assert reference_date_candidates(two_days, next_friday) == [fri, SAT]
    _, ref = departure_curve_with_reference(two_days, next_friday, window_min=30)
    assert ref == fri

    sunday = datetime(2026, 10, 25, 12, tzinfo=LONDON)
    assert reference_date_candidates(two_days, sunday) == [SAT, fri]


def test_no_recorded_day_covers_the_time(timetable: Segments) -> None:
    night = datetime(2026, 10, 27, 3, tzinfo=LONDON)  # recordings are 06:00-23:00
    curve, ref = departure_curve_with_reference(timetable, night, window_min=30)
    assert ref is None
    assert not np.isfinite(curve.p_on_time).any()


# --- two-leg journeys with one change --------------------------------------


def _brute_transfer(first, second, reach, instants, deadline, walk_from_s, gap_s, buf_s):
    """Loop version of replay_transfer_curve's rules, for one departure row."""
    def board(seg, t):
        for (a, b) in seg.coverage:
            if a <= t <= b:
                for k, o in enumerate(seg.t_origin):
                    if o >= t:
                        return k if o <= b else None
                return None
        return None

    arrivals = []
    for s in instants:
        k1 = board(first, s + buf_s)
        if k1 is None:
            continue
        k2 = board(second, first.t_dest[k1] + gap_s + buf_s)
        if k2 is None:
            continue
        arrivals.append(reach + second.t_dest[k2] - s + walk_from_s)
    return arrivals


def test_transfer_matches_a_hand_checked_connection() -> None:
    # Leg 1 every 10 min, 20 min ride; leg 2 every 15 min from :05, 10 min ride;
    # fifteen recorded days so the single replayed instant has 15 distinct runs.
    last = END + timedelta(days=14)
    first = synthetic_segments(START, last, headway_min=10, ride_min=20)
    second = synthetic_segments(
        START + timedelta(minutes=5), last, headway_min=15, ride_min=10
    )

    def leave_at_10(deadline: datetime):
        return replay_transfer_curve(
            first, second, np.array([to_epoch(at(10, 0))]), to_epoch(deadline),
            tod_window_min=0, board_buffer_min=0, transfer_min=3,
            reference_dates=FIFTEEN_DAYS, n_boot=0,
        )

    # 10:00 bus reaches X 10:20; 3 min later the next leg-2 bus is 10:35 -> 10:45.
    on_time = leave_at_10(at(10, 45))
    assert on_time.n_trips[0] == 15 and on_time.status[0] == "ok"
    assert on_time.p_on_time[0] == 1.0
    assert on_time.arrive_p50[0] == to_epoch(at(10, 45))
    assert leave_at_10(at(10, 44)).p_on_time[0] == 0.0


def test_transfer_matches_a_brute_force_replay() -> None:
    first = synthetic_segments(
        START, END, headway_min=8, ride_min=18, headway_jitter_min=3,
        ride_jitter_min=4, seed=3,
    )
    second = synthetic_segments(
        START, END, headway_min=12, ride_min=9, headway_jitter_min=4,
        ride_jitter_min=2, seed=4,
    )
    deadline = to_epoch(at(13, 0))
    depart = np.array([to_epoch(at(11, m)) for m in (0, 17, 33, 48)])
    curve = replay_transfer_curve(
        first, second, depart, deadline, walk_to_min=4, transfer_min=2,
        walk_from_min=3, tod_window_min=30, n_boot=0,
    )
    for i, d in enumerate(depart):
        reach = d + 240
        instants = [reach + k * 60 for k in range(-30, 31)]
        arrivals = _brute_transfer(first, second, reach, instants, deadline, 180, 120, 60)
        assert curve.n_steps[i] == len(arrivals)
        assert curve.p_on_time[i] == pytest.approx(
            sum(a <= deadline for a in arrivals) / len(arrivals)
        )
        assert curve.arrive_p50[i] == pytest.approx(np.percentile(arrivals, 50))


def test_transfer_is_censored_when_the_second_leg_is_not_recorded() -> None:
    first = synthetic_segments(START, END, headway_min=10, ride_min=20)
    second = synthetic_segments(START, at(10, 0), headway_min=10, ride_min=10)
    curve = replay_transfer_curve(
        first, second, np.array([to_epoch(at(11, 0))]), to_epoch(at(12, 0)), n_boot=0
    )
    assert curve.n_steps[0] == 0
    assert curve.status[0] == "insufficient_data"


def test_transfer_borrows_only_days_both_legs_recorded() -> None:
    fri_start = datetime(2026, 10, 23, 6, tzinfo=LONDON)
    first = synthetic_segments(fri_start, END, headway_min=10, ride_min=20)
    second = synthetic_segments(START, END, headway_min=10, ride_min=10)  # Sat only
    next_friday = datetime(2026, 10, 30, 12, tzinfo=LONDON)
    curve, ref = transfer_curve_with_reference(first, second, next_friday, window_min=30)
    assert ref == SAT  # Friday has no second leg, so the shared Saturday is used
    assert np.isfinite(curve.p_on_time).any()
