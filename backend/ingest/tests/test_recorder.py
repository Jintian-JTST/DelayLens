import json
from datetime import UTC, datetime, timedelta
from unittest.mock import patch

import pytest
from ingest.database_poller import (
    FetchFailure,
    backup,
    fetch,
    normalize,
    read_batch,
    utc,
)
from ingest.derive import advance
from ingest.settings import Settings, load_routes

T = datetime(2026, 10, 25, 0, 59, tzinfo=UTC)


def prediction(**changes):
    result = {
        "id": "p1", "vehicleId": "bus-123", "lineId": "29", "naptanId": "490000083S",
        "direction": "outbound", "timeToStation": 40,
        "expectedArrival": (T + timedelta(seconds=40)).isoformat(), "timestamp": T.isoformat(),
        "tripId": "trip1",
    }
    result.update(changes)
    return result


def settings(tmp_path):
    return Settings(("29",), frozenset({"490000083S"}), 30, tmp_path)


def row(seconds=0, **changes):
    result = {
        "polled_at": (T + timedelta(seconds=seconds)).isoformat(),
        "line_id": "29", "direction": "outbound", "vehicle_id": "bus-123",
        "naptan_id": "490000083S", "prediction_id": "p1", "time_to_station": 40,
        "expected_arrival": (T + timedelta(seconds=seconds + 40)).isoformat(), "trip_id": "trip1",
    }
    result.update(changes)
    return result


def test_route_contract():
    routes = load_routes()
    assert len(routes) == 4
    assert {r["mode"] for r in routes} == {"bus", "tube"}
    assert len({r["route_id"] for r in routes}) == 4
    assert {r["direction"] for r in routes} == {"inbound", "outbound"}


@pytest.mark.parametrize("change", [
    {"vehicleId": "000"}, {"vehicleId": None}, {"direction": None},
    {"timeToStation": -1}, {"timeToStation": True}, {"timestamp": "2026-10-25"},
    {"expectedArrival": "bad"}, {"timestamp": (T - timedelta(seconds=181)).isoformat()},
    {"timestamp": (T + timedelta(seconds=61)).isoformat()},
    {"lineId": []}, {"naptanId": {}}, {"id": None},
])
def test_reject_invalid_selected_predictions(tmp_path, change):
    kept, rejected = normalize([prediction(**change)], T.isoformat(), settings(tmp_path))
    assert kept == []
    assert rejected == 1


def test_filter_and_deduplicate(tmp_path):
    p = prediction()
    kept, rejected = normalize([p, p, prediction(lineId="73"), prediction(naptanId="elsewhere")], T.isoformat(), settings(tmp_path))
    assert len(kept) == 1
    assert rejected == 0


def test_backup_survives_without_database_and_preserves_rejected_rows(tmp_path):
    path, batch = backup(settings(tmp_path), [prediction(), prediction(vehicleId="000")], T.isoformat())
    assert path.name.endswith(".jsonl.gz")
    restored = read_batch(path)
    assert restored["batch_id"] == batch["batch_id"]
    assert len(restored["raw_predictions"]) == 2
    assert len(restored["rows"]) == 1
    assert not list(tmp_path.rglob("*.tmp"))


def test_near_stop_uses_last_near_eta_only_after_absence():
    state, events = advance({}, [row(), row(30, time_to_station=25,
        expected_arrival=(T + timedelta(seconds=55)).isoformat())], (T + timedelta(seconds=60)).isoformat())
    assert events == []
    _, events = advance(state, [], (T + timedelta(seconds=120)).isoformat())
    assert events[0]["observed_at"] == (T + timedelta(seconds=55)).isoformat()
    assert events[0]["method"] == "near_stop_prediction"
    assert events[0]["samples"] == 2


def test_no_near_prediction_falls_back_to_last_poll():
    _, events = advance({}, [row(time_to_station=200)], (T + timedelta(seconds=90)).isoformat())
    assert events[0]["observed_at"] == T.isoformat()
    assert events[0]["method"] == "last_poll"
    assert events[0]["last_time_to_station"] == 200


def test_repeat_vehicle_after_twenty_minutes_is_new_episode():
    _, events = advance({}, [row(), row(1300)], (T + timedelta(seconds=1400)).isoformat())
    assert len(events) == 2
    assert len({e["episode_started_at"] for e in events}) == 2


def test_trip_identity_change_splits_episode():
    _, events = advance({}, [row(), row(300, trip_id="trip2")], (T + timedelta(seconds=400)).isoformat())
    assert {e["trip_id"] for e in events} == {"trip1", "trip2"}


def test_direction_and_line_are_part_of_identity():
    _, events = advance({}, [row(), row(direction="inbound"), row(line_id="victoria")], (T + timedelta(seconds=100)).isoformat())
    assert len(events) == 3


def test_episode_state_roundtrip_and_incremental_replay():
    full, events_full = advance({}, [row(), row(30)], (T + timedelta(seconds=120)).isoformat())
    state, _ = advance({}, [row()], T.isoformat())
    state = json.loads(json.dumps(state))
    split, events_split = advance(state, [row(30)], (T + timedelta(seconds=120)).isoformat())
    assert split == full
    assert events_split == events_full


def test_fall_back_hour_is_two_distinct_utc_hours():
    first = utc("2026-10-25T01:30:00+01:00")
    second = utc("2026-10-25T01:30:00+00:00")
    assert second - first == timedelta(hours=1)
    with pytest.raises(ValueError, match="Naive"):
        utc("2026-10-25T01:30:00")


def test_network_failure_is_not_empty_success(tmp_path):
    with patch("urllib.request.urlopen", side_effect=TimeoutError("must not appear")), pytest.raises(FetchFailure) as captured:
        fetch(settings(tmp_path))
    assert "must not appear" not in str(captured.value)
