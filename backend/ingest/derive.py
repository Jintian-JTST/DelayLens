"""Incrementally infer estimated stop events and expose SQL-matched trip segments.

An estimated event follows PLAN §3.2: last near-stop ETA (horizon <=60s),
otherwise last seen poll. It is finalized only after successful polls show its
absence for >=90s. These estimates are not ground-truth vehicle telemetry.
"""

import json
from datetime import timedelta

from .database_poller import utc

EPISODE_GAP = timedelta(minutes=20)
ABSENCE = timedelta(seconds=90)
EVENT_COLUMNS = (
    "line_id", "direction", "vehicle_id", "naptan_id", "episode_started_at",
    "observed_at", "first_polled_at", "last_polled_at", "method", "samples",
    "last_time_to_station", "trip_id",
)


def key_for(row: dict) -> str:
    return json.dumps([row[k] for k in ("line_id", "direction", "vehicle_id", "naptan_id")], separators=(",", ":"))


def event_from(episode: dict) -> dict:
    event = {k: episode[k] for k in EVENT_COLUMNS if k in episode}
    near = episode.get("near_expected_arrival")
    event["observed_at"] = near or episode["last_polled_at"]
    event["method"] = "near_stop_prediction" if near else "last_poll"
    return event


def advance(episodes: dict, rows: list[dict], watermark: str) -> tuple[dict, list[dict]]:
    """Pure deterministic episode state transition, shared by live and replay."""
    events = {}
    for row in sorted(rows, key=lambda r: (utc(r["polled_at"]), r["prediction_id"])):
        key = key_for(row)
        episode = episodes.get(key)
        polled = utc(row["polled_at"])
        changed_trip = bool(episode and episode.get("trip_id") and row.get("trip_id")
                            and episode["trip_id"] != row["trip_id"])
        # A train ID can be recycled. A near-stop episode followed by a much
        # later ETA after disappearance must not merge two physical trips.
        recycled = bool(episode and episode.get("near_expected_arrival")
                        and polled - utc(episode["last_polled_at"]) >= ABSENCE
                        and utc(row["expected_arrival"]) - utc(episode["near_expected_arrival"]) > timedelta(minutes=5))
        if episode and (polled - utc(episode["last_polled_at"]) > EPISODE_GAP or changed_trip or recycled):
            event = event_from(episode)
            events[(key, event["episode_started_at"])] = event
            episode = None
        if episode is None:
            episode = {k: row[k] for k in ("line_id", "direction", "vehicle_id", "naptan_id")}
            episode.update(episode_started_at=row["polled_at"], first_polled_at=row["polled_at"],
                           samples=0, trip_id=row.get("trip_id"))
            episodes[key] = episode
        # Multiple same-stop predictions in a response count as one observed poll.
        if episode.get("last_polled_at") != row["polled_at"]:
            episode["samples"] += 1
        episode["last_polled_at"] = row["polled_at"]
        episode["last_time_to_station"] = row["time_to_station"]
        if row["time_to_station"] <= 60:
            episode["near_expected_arrival"] = row["expected_arrival"]
        episode["trip_id"] = row.get("trip_id") or episode.get("trip_id")
    for key, episode in list(episodes.items()):
        age = utc(watermark) - utc(episode["last_polled_at"])
        if age >= ABSENCE:
            event = event_from(episode)
            # Do not finalize an ETA still in the future after a disappearance.
            if utc(event["observed_at"]) <= utc(watermark):
                events[(key, event["episode_started_at"])] = event
        if age > EPISODE_GAP:
            del episodes[key]
    return episodes, list(events.values())


def derive_database(connection) -> int:
    from psycopg.rows import dict_row
    from psycopg.types.json import Jsonb

    with connection.transaction(), connection.cursor(row_factory=dict_row) as cursor:
        cursor.execute("SELECT last_processed_at, episodes FROM derivation_state WHERE singleton FOR UPDATE")
        state = cursor.fetchone()
        cursor.execute("SELECT max(polled_at) AS watermark FROM poll_runs")
        watermark = cursor.fetchone()["watermark"]
        if watermark is None:
            return 0
        rebuilding = state["last_processed_at"] is None
        cursor.execute("""
            SELECT * FROM arrival_predictions
            WHERE (%s::timestamptz IS NULL OR polled_at > %s::timestamptz)
            ORDER BY polled_at, prediction_id
        """, (state["last_processed_at"], state["last_processed_at"]))
        rows = cursor.fetchall()
        for row in rows:
            for column in ("polled_at", "expected_arrival", "source_timestamp"):
                row[column] = row[column].isoformat()
        episodes, events = advance(state["episodes"], rows, watermark.isoformat())
        if rebuilding:
            # Atomic rebuild from retained raw data; readers see old or new events.
            cursor.execute("DELETE FROM stop_events")
        if events:
            cursor.executemany("""
                INSERT INTO stop_events (
                    line_id,direction,vehicle_id,naptan_id,episode_started_at,
                    observed_at,first_polled_at,last_polled_at,method,samples,
                    last_time_to_station,trip_id
                ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                ON CONFLICT (line_id,direction,vehicle_id,naptan_id,episode_started_at)
                DO UPDATE SET observed_at=EXCLUDED.observed_at,
                    last_polled_at=EXCLUDED.last_polled_at, method=EXCLUDED.method,
                    samples=EXCLUDED.samples, last_time_to_station=EXCLUDED.last_time_to_station,
                    trip_id=EXCLUDED.trip_id
            """, [tuple(e[c] for c in EVENT_COLUMNS) for e in events])
        cursor.execute("UPDATE derivation_state SET last_processed_at=%s, episodes=%s WHERE singleton",
                       (watermark, Jsonb(episodes)))
    return len(events)


def main() -> int:
    import logging

    from .settings import load_env
    from .store import connect, database_errors

    load_env()
    try:
        with connect() as connection:
            count = derive_database(connection)
        print(f"Derived event upserts: {count}")
        return 0
    except database_errors() as exc:
        logging.getLogger("delaylens.ingest.derive").error("Derivation failed type=%s", type(exc).__name__)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
