"""30-second recorder. Run from backend: python -m ingest.database_poller.

Every successful response is durably backed up before attempting database writes.
Unacknowledged files remain pending and replay automatically after an outage.
"""

import argparse
import gzip
import json
import logging
import os
import signal
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path

from .settings import Settings, load_env
from .store import database_errors

LOG = logging.getLogger("delaylens.ingest")
STOP = threading.Event()


def utc(value: str) -> datetime:
    result = datetime.fromisoformat(value)
    if result.tzinfo is None:
        raise ValueError("Naive timestamp")
    return result.astimezone(UTC)


def selected(item: object, settings: Settings) -> bool:
    return (isinstance(item, dict) and isinstance(item.get("lineId"), str)
            and isinstance(item.get("naptanId"), str)
            and item["lineId"] in settings.line_ids and item["naptanId"] in settings.stop_ids)


def normalize(predictions: list, polled_at: str, settings: Settings) -> tuple[list[dict], int]:
    """Reject unusable identities and fields; never turn a failure into a row."""
    rows: dict[tuple, dict] = {}
    rejected = 0
    for item in predictions:
        if (not isinstance(item, dict) or not isinstance(item.get("lineId"), str)
                or not isinstance(item.get("naptanId"), str)):
            rejected += 1
            continue
        if not selected(item, settings):
            continue
        try:
            vehicle = str(item["vehicleId"]).strip()
            if not vehicle or vehicle.lower() in {"0", "000", "0000", "unknown", "none", "null"}:
                raise ValueError("Unusable vehicle")
            direction = item.get("direction")
            if direction not in {"inbound", "outbound"}:
                raise ValueError("Missing direction")
            tts = item["timeToStation"]
            if type(tts) is not int or tts < 0:
                raise ValueError("Invalid horizon")
            expected = utc(item["expectedArrival"])
            source = utc(item["timestamp"])
            polled = utc(polled_at)
            if source > polled + timedelta(seconds=60):
                raise ValueError("Future source timestamp")
            if (polled - source).total_seconds() > 180:
                raise ValueError("Stale prediction")
            if not -90 <= (expected - polled).total_seconds() <= 7200:
                raise ValueError("Invalid prediction window")
            if type(item["id"]) not in {str, int} or not str(item["id"]):
                raise ValueError("Missing prediction id")
            prediction_id = str(item["id"])
            row = {
                "polled_at": polled.isoformat(), "line_id": item["lineId"],
                "direction": direction, "vehicle_id": vehicle, "naptan_id": item["naptanId"],
                "destination_name": item.get("destinationName"), "time_to_station": tts,
                "expected_arrival": expected.isoformat(), "source_timestamp": source.isoformat(),
                "prediction_id": prediction_id, "trip_id": item.get("tripId") or None,
                "destination_naptan_id": item.get("destinationNaptanId") or None,
            }
            key = (row["line_id"], direction, vehicle, row["naptan_id"], prediction_id)
            rows[key] = row
        except (KeyError, TypeError, ValueError, OverflowError):
            rejected += 1
    return list(rows.values()), rejected


class FetchFailure(Exception):
    def __init__(self, status: int | None = None, retry_after: float = 0):
        self.status = status
        self.retry_after = retry_after


def fetch(settings: Settings) -> list:
    # Key only travels to the official API. Never log request URLs or exceptions.
    query = urllib.parse.urlencode({"app_key": os.getenv("TFL_APP_KEY", "")})
    request = urllib.request.Request(
        "https://api.tfl.gov.uk/Line/" + ",".join(settings.line_ids) + "/Arrivals?" + query,
        headers={"User-Agent": "DelayLens/0.1", "Accept": "application/json"},
    )
    try:
        with urllib.request.urlopen(request, timeout=12) as response:
            payload = response.read(20_000_001)
            if len(payload) > 20_000_000:
                raise FetchFailure()
            data = json.loads(payload)
        if not isinstance(data, list):
            raise FetchFailure()
        return data
    except urllib.error.HTTPError as exc:
        try:
            retry = max(0, min(600, float(exc.headers.get("Retry-After", "0"))))
        except (TypeError, ValueError):
            retry = 0
        raise FetchFailure(exc.code, retry) from None
    except (urllib.error.URLError, TimeoutError, OSError, ValueError):
        raise FetchFailure() from None


def backup(settings: Settings, predictions: list, polled_at: str) -> tuple[Path, dict]:
    rows, rejected = normalize(predictions, polled_at, settings)
    batch = {
        "format_version": 1, "batch_id": uuid.uuid4().hex, "polled_at": polled_at,
        "line_ids": settings.line_ids, "stop_ids": sorted(settings.stop_ids),
        "predictions_received": len(predictions), "predictions_rejected": rejected,
        # Preserve the filtered raw payload, even rows normalization rejects.
        "raw_predictions": [p for p in predictions if selected(p, settings)],
        "rows": rows,
    }
    pending = settings.backup_dir / "pending"
    pending.mkdir(parents=True, exist_ok=True)
    stamp = utc(polled_at).strftime("%Y%m%dT%H%M%S.%fZ")
    target = pending / f"{stamp}-{batch['batch_id']}.jsonl.gz"
    temporary = target.with_suffix(".tmp")
    data = (json.dumps(batch, separators=(",", ":")) + "\n").encode("utf-8")
    with temporary.open("wb") as handle:
        with gzip.GzipFile(fileobj=handle, mode="wb", mtime=0) as compressed:
            compressed.write(data)
        handle.flush()
        os.fsync(handle.fileno())
    temporary.replace(target)
    return target, batch


def read_batch(path: Path) -> dict:
    with gzip.open(path, "rt", encoding="utf-8") as handle:
        batch = json.loads(handle.readline())
        if handle.read().strip() or batch.get("format_version") != 1:
            raise ValueError("Unsupported backup")
    return batch


def flush_pending(settings: Settings, limit: int = 20) -> int:
    from .store import connect, ingest_batch, sync_routes

    paths = sorted((settings.backup_dir / "pending").glob("*.jsonl.gz"))[:limit]
    if not paths:
        return 0
    count = 0
    with connect() as connection:
        sync_routes(connection)
        for path in paths:
            batch = read_batch(path)
            ingest_batch(connection, batch)
            # A crash before this move is harmless: poll_runs makes replay idempotent.
            archive = settings.backup_dir / "archive" / utc(batch["polled_at"]).strftime("%Y-%m-%d")
            archive.mkdir(parents=True, exist_ok=True)
            path.replace(archive / path.name)
            count += 1
    return count


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--once", action="store_true", help="Fetch and back up one poll, then exit")
    parser.add_argument("--backup-only", action="store_true", help="Explicitly disable database writes")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)sZ %(levelname)s %(message)s")
    logging.Formatter.converter = time.gmtime
    load_env()
    settings = Settings.read()
    for sig in (signal.SIGINT, signal.SIGTERM):
        signal.signal(sig, lambda *_: STOP.set())
    failures = 0
    while not STOP.is_set():
        started = time.monotonic()
        wait = settings.interval
        poll_failed = False
        try:
            predictions = fetch(settings)
            polled_at = datetime.now(UTC).isoformat()
            _, batch = backup(settings, predictions, polled_at)
            LOG.info("backup_ok received=%d kept=%d rejected=%d", len(predictions), len(batch["rows"]), batch["predictions_rejected"])
            failures = 0
        except FetchFailure as exc:
            poll_failed = True
            failures += 1
            wait = max(wait, exc.retry_after, min(300, settings.interval * 2 ** min(failures - 1, 4)))
            LOG.warning("tfl_failed status=%s retry_in_seconds=%.0f", exc.status or "network_or_payload", wait)
        except OSError:
            # A backup disk failure must be visible, never acknowledge success.
            LOG.error("backup_failed; recorder stopped to avoid unbacked ingestion")
            return 1
        db_failed = False
        if not args.backup_only and os.getenv("DATABASE_URL"):
            try:
                committed = flush_pending(settings)
                LOG.info("database_batches_acknowledged=%d", committed)
                from .derive import derive_database
                from .store import connect
                with connect() as connection:
                    events = derive_database(connection)
                LOG.info("derived_events_upserted=%d", events)
            except database_errors() as exc:
                db_failed = True
                # Driver errors may include a connection string, password or URL.
                LOG.error("database_or_derive_failed type=%s; backups retained", type(exc).__name__)
        else:
            LOG.warning("database_not_connected; durable pending backups only")
        if args.once:
            return int(poll_failed or db_failed)
        STOP.wait(max(0, wait - (time.monotonic() - started)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
