"""Tiger Data access through D's views (docs/tasks/data-ingestion.md).

A background thread loads everything into an in-memory snapshot once a minute,
so request handlers never wait on the database (PLAN.md section 6.5).
"""

import logging
import threading
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime

import psycopg

from app.schemas import Stats

log = logging.getLogger(__name__)

REFRESH_SECONDS = 60
CONNECT_TIMEOUT_S = 10

SEGMENTS_SQL = """
SELECT route_id, vehicle_id, origin_observed_at, destination_observed_at, ride_seconds,
       origin_episode_started_at
FROM get_segments ORDER BY route_id, origin_observed_at
"""
COVERAGE_SQL = "SELECT route_id, trips_observed, hours_covered FROM route_coverage"
# Every departure seen at a route's origin, usable or not (D's stop_events).
ORIGIN_EVENTS_SQL = """
SELECT r.route_id, o.vehicle_id, o.episode_started_at, o.observed_at
FROM route_config r
JOIN stop_events o ON o.line_id = r.line_id AND o.direction = r.direction
                  AND o.naptan_id = r.origin_naptan_id
WHERE r.active ORDER BY r.route_id, o.observed_at
"""
POLLS_SQL = "SELECT polled_at FROM poll_runs ORDER BY polled_at"
ROWS_SQL = "SELECT count(*), min(polled_at), max(polled_at) FROM arrival_predictions"
CHUNKS_SQL = """
SELECT count(*) FROM timescaledb_information.chunks
WHERE hypertable_name = 'arrival_predictions'
"""
COMPRESSION_SQL = """
SELECT before_compression_total_bytes, after_compression_total_bytes
FROM hypertable_columnstore_stats('arrival_predictions')
"""


@dataclass(frozen=True)
class Segment:
    vehicle_id: str
    origin_observed_at: datetime
    destination_observed_at: datetime
    ride_seconds: float
    # With route_id and vehicle_id, the stable trip key D documents.
    origin_episode_started_at: datetime


@dataclass(frozen=True)
class Coverage:
    trips_observed: int
    hours_covered: list[datetime]


@dataclass(frozen=True)
class OriginEvent:
    vehicle_id: str
    episode_started_at: datetime
    observed_at: datetime


@dataclass(frozen=True)
class Snapshot:
    segments: dict[str, list[Segment]]
    coverage: dict[str, Coverage]
    origin_events: dict[str, list[OriginEvent]]
    poll_times: list[datetime]
    # None in offline snapshot mode: row and chunk counts are database facts.
    stats: Stats | None
    refreshed_at: datetime
    # Set only for an offline snapshot (SNAPSHOT_DIR); shown in the basis text.
    source_label: str | None = None


def load_snapshot(database_url: str) -> Snapshot:
    with psycopg.connect(database_url, connect_timeout=CONNECT_TIMEOUT_S) as conn:
        conn.read_only = True
        with conn.cursor() as cur:
            cur.execute("SET TIME ZONE 'UTC'")

            cur.execute(SEGMENTS_SQL)
            segments: dict[str, list[Segment]] = {}
            for route_id, vehicle_id, origin, destination, ride, episode in cur.fetchall():
                segments.setdefault(route_id, []).append(
                    Segment(vehicle_id, origin, destination, float(ride), episode)
                )

            cur.execute(COVERAGE_SQL)
            coverage = {
                route_id: Coverage(int(trips), list(hours or []))
                for route_id, trips, hours in cur.fetchall()
            }

            cur.execute(ORIGIN_EVENTS_SQL)
            origin_events: dict[str, list[OriginEvent]] = {}
            for route_id, vehicle_id, episode, observed in cur.fetchall():
                origin_events.setdefault(route_id, []).append(
                    OriginEvent(vehicle_id, episode, observed)
                )

            cur.execute(POLLS_SQL)
            poll_times = [row[0] for row in cur.fetchall()]

            cur.execute(ROWS_SQL)
            rows, first_polled, last_polled = cur.fetchone()
            cur.execute(CHUNKS_SQL)
            (chunks,) = cur.fetchone()
            cur.execute(COMPRESSION_SQL)
            before, after = cur.fetchone() or (None, None)

    ratio = round(before / after, 2) if before and after else None
    return Snapshot(
        segments=segments,
        coverage=coverage,
        origin_events=origin_events,
        poll_times=poll_times,
        stats=Stats(
            rows=rows,
            chunks=chunks,
            compression_ratio=ratio,
            first_polled_at=first_polled,
            last_polled_at=last_polled,
        ),
        refreshed_at=datetime.now(UTC),
    )


class SegmentCache:
    """Latest good snapshot; a failed refresh keeps serving the previous one."""

    def __init__(
        self,
        database_url: str,
        *,
        loader: Callable[[str], Snapshot] = load_snapshot,
        interval_s: float = REFRESH_SECONDS,
    ) -> None:
        self._url = database_url
        self._loader = loader
        self._interval_s = interval_s
        self._snapshot: Snapshot | None = None
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self.last_error: str | None = None

    @property
    def snapshot(self) -> Snapshot | None:
        return self._snapshot

    def segments(self, route_id: str) -> list[Segment]:
        return self._snapshot.segments.get(route_id, []) if self._snapshot else []

    def refresh(self) -> bool:
        try:
            self._snapshot = self._loader(self._url)
        except (psycopg.Error, OSError) as exc:
            # Log the error type only: connection errors can include the host.
            self.last_error = type(exc).__name__
            log.warning("Tiger Data refresh failed: %s", self.last_error)
            return False
        self.last_error = None
        return True

    def start(self) -> None:
        if self._thread is not None:
            return
        self._thread = threading.Thread(target=self._run, name="segment-cache", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()

    def _run(self) -> None:
        while not self._stop.is_set():
            self.refresh()
            self._stop.wait(self._interval_s)


class FrozenCache:
    """SegmentCache stand-in for offline snapshot mode: one fixed snapshot, no database."""

    last_error: str | None = None

    def __init__(self, snapshot: Snapshot) -> None:
        self._snapshot = snapshot

    @property
    def snapshot(self) -> Snapshot:
        return self._snapshot

    def segments(self, route_id: str) -> list[Segment]:
        return self._snapshot.segments.get(route_id, [])

    def start(self) -> None:
        pass

    def stop(self) -> None:
        pass
