"""Transactional database writes with replay deduplication; never log credentials."""

import os

from .settings import load_routes


def database_errors() -> tuple[type[Exception], ...]:
    try:
        import psycopg
    except ImportError:
        return (OSError, ValueError, ImportError, RuntimeError)
    return (psycopg.Error, OSError, ValueError, ImportError, RuntimeError)

PREDICTION_COLUMNS = (
    "polled_at", "line_id", "direction", "vehicle_id", "naptan_id",
    "destination_name", "time_to_station", "expected_arrival", "source_timestamp",
    "prediction_id", "trip_id", "destination_naptan_id",
)
INSERT_PREDICTIONS = """
INSERT INTO arrival_predictions (
    polled_at, line_id, direction, vehicle_id, naptan_id, destination_name,
    time_to_station, expected_arrival, source_timestamp, prediction_id, trip_id,
    destination_naptan_id
) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) ON CONFLICT DO NOTHING
"""


def connect():
    import psycopg

    url = os.getenv("DATABASE_URL", "")
    if not url or "user:password@host" in url:
        raise ValueError("DATABASE_URL is not configured")
    return psycopg.connect(
        url, autocommit=True, connect_timeout=8,
        options="-c timezone=UTC -c statement_timeout=20000 -c lock_timeout=5000",
        application_name="delaylens-recorder",
    )


def sync_routes(connection) -> None:
    with connection.transaction(), connection.cursor() as cursor:
        cursor.execute("UPDATE route_config SET active = FALSE")
        cursor.executemany("""
            INSERT INTO route_config
                (route_id,line_id,direction,mode,origin_naptan_id,destination_naptan_id,active)
            VALUES (%s,%s,%s,%s,%s,%s,TRUE)
            ON CONFLICT (route_id) DO UPDATE SET
                line_id=EXCLUDED.line_id, direction=EXCLUDED.direction,
                mode=EXCLUDED.mode, origin_naptan_id=EXCLUDED.origin_naptan_id,
                destination_naptan_id=EXCLUDED.destination_naptan_id, active=TRUE
        """, [(r["route_id"], r["line_id"], r["direction"], r["mode"],
               r["origin"]["naptan_id"], r["destination"]["naptan_id"]) for r in load_routes()])


def ingest_batch(connection, batch: dict) -> bool:
    with connection.transaction(), connection.cursor() as cursor:
        cursor.execute("SELECT 1 FROM poll_runs WHERE batch_id=%s", (batch["batch_id"],))
        if cursor.fetchone():
            return False
        cursor.executemany(INSERT_PREDICTIONS,
                           [tuple(row[c] for c in PREDICTION_COLUMNS) for row in batch["rows"]])
        cursor.execute("""
            INSERT INTO poll_runs VALUES (%s,%s,%s,%s,%s)
            ON CONFLICT (batch_id) DO NOTHING
        """, (batch["batch_id"], batch["polled_at"], batch["predictions_received"],
               len(batch["rows"]), batch["predictions_rejected"]))
        # Out-of-order backfill must also be incorporated into inferred episodes.
        cursor.execute("""
            UPDATE derivation_state SET last_processed_at=NULL, episodes='{}'::jsonb
            WHERE singleton AND last_processed_at >= %s::timestamptz
        """, (batch["polled_at"],))
    return True
