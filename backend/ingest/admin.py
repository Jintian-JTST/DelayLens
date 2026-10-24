"""Secret-safe schema setup, backup replay, derivation and data health checks."""

import argparse
import gzip
import json
import logging
from datetime import UTC, datetime
from pathlib import Path

from .derive import derive_database
from .database_poller import flush_pending, read_batch
from .settings import BACKEND, PROJECT, Settings, load_env, load_routes
from .store import connect, database_errors, ingest_batch, sync_routes

LOG = logging.getLogger("delaylens.ingest.admin")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["init", "replay", "derive", "health", "verify-backups", "snapshot"])
    parser.add_argument("--include-archive", action="store_true", help="Replay archived batches too")
    parser.add_argument("--output", type=Path, default=PROJECT / ".local" / "delaylens-snapshot.json.gz")
    args = parser.parse_args()
    load_env()
    settings = Settings.read()
    try:
        if args.command == "verify-backups":
            files = sorted(settings.backup_dir.rglob("*.jsonl.gz"))
            rows = 0
            batches = []
            for path in files:
                batch = read_batch(path)
                rows += len(batch["rows"])
                batches.append(batch["polled_at"])
            print(json.dumps({"backup_files": len(files), "normalized_rows": rows,
                              "first_poll": min(batches) if batches else None,
                              "last_poll": max(batches) if batches else None}))
            return 0
        with connect() as connection:
            if args.command == "init":
                connection.execute((BACKEND / "sql" / "001_schema.sql").read_text(encoding="utf-8"))
                sync_routes(connection)
                print("Schema initialized and configured routes synchronized")
            elif args.command == "replay":
                sync_routes(connection)
                archived = 0
                if args.include_archive:
                    for path in sorted((settings.backup_dir / "archive").rglob("*.jsonl.gz")):
                        archived += int(ingest_batch(connection, read_batch(path)))
                pending = flush_pending(settings, limit=1_000_000)
                events = derive_database(connection)
                print(json.dumps({"archived_batches_inserted": archived,
                                  "pending_batches_acknowledged": pending, "event_upserts": events}))
            elif args.command == "derive":
                print(json.dumps({"event_upserts": derive_database(connection)}))
            elif args.command == "snapshot":
                from psycopg.rows import dict_row

                with connection.transaction(), connection.cursor(row_factory=dict_row) as cursor:
                    cursor.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY")
                    cursor.execute("SELECT * FROM get_segments ORDER BY route_id,origin_observed_at")
                    segments = cursor.fetchall()
                    cursor.execute("SELECT * FROM route_coverage ORDER BY route_id")
                    coverage = cursor.fetchall()
                snapshot = {"format_version": 1, "generated_at": datetime.now(UTC).isoformat(),
                            "provenance": "TfL prediction-derived estimates, not measured arrivals",
                            "routes": load_routes(), "segments": segments, "coverage": coverage}
                args.output.parent.mkdir(parents=True, exist_ok=True)
                temporary = args.output.with_suffix(".tmp")
                with gzip.open(temporary, "wt", encoding="utf-8") as handle:
                    json.dump(snapshot, handle, default=lambda value: value.isoformat())
                temporary.replace(args.output)
                print(json.dumps({"snapshot_written": True, "segments": len(segments)}))
            else:
                from psycopg.rows import dict_row
                with connection.cursor(row_factory=dict_row) as cursor:
                    cursor.execute("""
                        SELECT count(*) AS prediction_rows, min(polled_at) AS first_polled_at,
                               max(polled_at) AS last_polled_at,
                               EXTRACT(EPOCH FROM now()-max(polled_at)) AS seconds_since_last_poll
                        FROM arrival_predictions
                    """)
                    health = dict(cursor.fetchone())
                    cursor.execute("SELECT * FROM route_coverage ORDER BY route_id")
                    health["route_coverage"] = cursor.fetchall()
                    cursor.execute("SELECT extversion FROM pg_extension WHERE extname='timescaledb'")
                    health["timescaledb"] = cursor.fetchone()
                    cursor.execute("SELECT count(*) AS stop_events FROM stop_events")
                    health.update(cursor.fetchone())
                    print(json.dumps(health, default=str))
        return 0
    except database_errors() as exc:
        # Don't emit traceback/driver message: it may contain credentials.
        LOG.error("Command failed type=%s; configuration values hidden", type(exc).__name__)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
