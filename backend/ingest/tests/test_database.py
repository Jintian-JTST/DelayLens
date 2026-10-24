"""Opt-in real TimescaleDB checks; every test is rolled back."""

import os
import uuid
from datetime import UTC, datetime, timedelta

import pytest

from ingest.database_derive import derive_database
from ingest.settings import load_env
from ingest.store import connect, ingest_batch

pytestmark = [pytest.mark.live_db, pytest.mark.skipif(
    os.getenv("INGEST_RUN_DB_TESTS") != "1", reason="Set INGEST_RUN_DB_TESTS=1 to opt into rollback-only DB checks")]


@pytest.fixture
def database():
    load_env()
    with connect() as connection, connection.transaction(force_rollback=True):
        yield connection


@pytest.fixture
def route(database):
    name = "test-" + uuid.uuid4().hex
    database.execute("""
        INSERT INTO route_config (route_id,line_id,direction,mode,origin_naptan_id,destination_naptan_id)
        VALUES (%s,%s,'outbound','bus','test-origin','test-destination')
    """, (name, name))
    return name


def event(connection, route, stop, minute, *, direction="outbound", method="near_stop_prediction", tts=10, vehicle="test-vehicle", trip=None):
    when = datetime(2026, 10, 25, 0, 0, tzinfo=UTC) + timedelta(minutes=minute)
    connection.execute("""
        INSERT INTO stop_events (line_id,direction,vehicle_id,naptan_id,episode_started_at,
            observed_at,first_polled_at,last_polled_at,method,samples,last_time_to_station,trip_id)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,3,%s,%s)
    """, (route, direction, vehicle, stop, when, when, when, when, method, tts, trip))


def segments(connection, route):
    return connection.execute("""
        SELECT route_id,vehicle_id,origin_observed_at,destination_observed_at,ride_seconds
        FROM get_segments WHERE route_id=%s ORDER BY origin_observed_at
    """, (route,)).fetchall()


def test_pair_direction_time_and_coverage(database, route):
    event(database, route, "test-origin", 0)
    event(database, route, "test-destination", 32, direction="inbound")
    assert segments(database, route) == []
    event(database, route, "test-destination", 35)
    result = segments(database, route)
    assert len(result) == 1
    assert result[0][4] == 35 * 60
    assert result[0][2].utcoffset() == timedelta(0)
    coverage = database.execute("SELECT trips_observed,hours_covered FROM route_coverage WHERE route_id=%s", (route,)).fetchone()
    assert coverage[0] == 1
    assert coverage[1] == [datetime(2026, 10, 25, 0, 0, tzinfo=UTC)]


def test_no_reuse_of_destination_or_crossing_new_origin(database, route):
    event(database, route, "test-origin", 0)
    event(database, route, "test-origin", 20)
    event(database, route, "test-destination", 35)
    result = segments(database, route)
    assert len(result) == 1
    assert result[0][2].minute == 20


def test_reused_vehicle_and_dst_hours(database, route):
    for start in (0, 60):
        event(database, route, "test-origin", start)
        event(database, route, "test-destination", start + 10)
    assert len(segments(database, route)) == 2
    coverage = database.execute("SELECT trips_observed,hours_covered FROM route_coverage WHERE route_id=%s", (route,)).fetchone()
    assert coverage[0] == 2
    assert len(coverage[1]) == 2


def test_long_horizon_disappearance_does_not_become_model_trip(database, route):
    event(database, route, "test-origin", 0, method="last_poll", tts=600)
    event(database, route, "test-destination", 30)
    assert segments(database, route) == []


def test_different_trip_ids_do_not_match(database, route):
    event(database, route, "test-origin", 0, trip="a")
    event(database, route, "test-destination", 30, trip="b")
    assert segments(database, route) == []


def test_routes_without_samples_get_empty_coverage(database, route):
    assert database.execute("SELECT trips_observed,hours_covered FROM route_coverage WHERE route_id=%s", (route,)).fetchone() == (0, [])


def test_replay_is_idempotent_and_derivation_is_incremental(database, route):
    # All rows and derivation state mutations are rolled back at fixture exit.
    stamp = datetime.now(UTC).replace(microsecond=0)
    row = {
        "polled_at": stamp.isoformat(), "line_id": route, "direction": "outbound",
        "vehicle_id": "test-vehicle", "naptan_id": "test-origin", "destination_name": None,
        "time_to_station": 20, "expected_arrival": (stamp + timedelta(seconds=20)).isoformat(),
        "source_timestamp": stamp.isoformat(), "prediction_id": uuid.uuid4().hex,
        "trip_id": None, "destination_naptan_id": None,
    }
    batch = {"batch_id": uuid.uuid4().hex, "polled_at": stamp.isoformat(),
             "predictions_received": 1, "predictions_rejected": 0, "rows": [row]}
    assert ingest_batch(database, batch)
    assert not ingest_batch(database, batch)
    assert database.execute("SELECT count(*) FROM arrival_predictions WHERE line_id=%s", (route,)).fetchone()[0] == 1
    future_batch = {**batch, "batch_id": uuid.uuid4().hex,
                    "polled_at": (stamp + timedelta(seconds=90)).isoformat(), "rows": []}
    ingest_batch(database, future_batch)
    derive_database(database)
    first = database.execute("SELECT observed_at,samples FROM stop_events WHERE line_id=%s", (route,)).fetchall()
    assert len(first) == 1
    derive_database(database)
    assert database.execute("SELECT observed_at,samples FROM stop_events WHERE line_id=%s", (route,)).fetchall() == first
