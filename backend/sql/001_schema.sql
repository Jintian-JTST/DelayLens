-- Verified against Tiger Data documentation on 2026-10-24; TimescaleDB >=2.18.
-- Apply once using: python -m ingest.admin init
-- Idempotent creation supports restart; it does not migrate incompatible schemas.
SET TIME ZONE 'UTC';
CREATE EXTENSION IF NOT EXISTS timescaledb;

CREATE TABLE IF NOT EXISTS arrival_predictions (
    polled_at timestamptz NOT NULL,
    line_id text NOT NULL,
    direction text NOT NULL CHECK (direction IN ('inbound', 'outbound')),
    vehicle_id text NOT NULL,
    naptan_id text NOT NULL,
    destination_name text,
    time_to_station integer NOT NULL CHECK (time_to_station >= 0),
    expected_arrival timestamptz NOT NULL,
    source_timestamp timestamptz NOT NULL,
    prediction_id text NOT NULL,
    trip_id text,
    destination_naptan_id text,
    PRIMARY KEY (polled_at, line_id, direction, vehicle_id, naptan_id, prediction_id)
);
SELECT create_hypertable('arrival_predictions',
    by_range('polled_at', INTERVAL '1 hour'), if_not_exists => TRUE);
CREATE INDEX IF NOT EXISTS predictions_vehicle_stop_time
    ON arrival_predictions (line_id, direction, vehicle_id, naptan_id, polled_at DESC);

-- Preserve successful empty polls and an atomic replay checkpoint per backup batch.
CREATE TABLE IF NOT EXISTS poll_runs (
    batch_id text PRIMARY KEY,
    polled_at timestamptz NOT NULL,
    predictions_received integer NOT NULL,
    predictions_kept integer NOT NULL,
    predictions_rejected integer NOT NULL
);
CREATE INDEX IF NOT EXISTS poll_runs_time ON poll_runs (polled_at DESC);

CREATE TABLE IF NOT EXISTS route_config (
    route_id text PRIMARY KEY,
    line_id text NOT NULL,
    direction text NOT NULL CHECK (direction IN ('inbound', 'outbound')),
    mode text NOT NULL CHECK (mode IN ('bus', 'tube')),
    origin_naptan_id text NOT NULL,
    destination_naptan_id text NOT NULL,
    active boolean NOT NULL DEFAULT TRUE
);

-- These are estimates from predictions, not ground-truth measured arrivals.
CREATE TABLE IF NOT EXISTS stop_events (
    line_id text NOT NULL,
    direction text NOT NULL,
    vehicle_id text NOT NULL,
    naptan_id text NOT NULL,
    episode_started_at timestamptz NOT NULL,
    observed_at timestamptz NOT NULL,
    first_polled_at timestamptz NOT NULL,
    last_polled_at timestamptz NOT NULL,
    method text NOT NULL CHECK (method IN ('near_stop_prediction', 'last_poll')),
    samples integer NOT NULL,
    last_time_to_station integer NOT NULL,
    trip_id text,
    PRIMARY KEY (line_id, direction, vehicle_id, naptan_id, episode_started_at)
);
CREATE INDEX IF NOT EXISTS events_matching
    ON stop_events (line_id, direction, vehicle_id, naptan_id, observed_at);

CREATE TABLE IF NOT EXISTS derivation_state (
    singleton boolean PRIMARY KEY DEFAULT TRUE CHECK (singleton),
    last_processed_at timestamptz,
    episodes jsonb NOT NULL DEFAULT '{}'::jsonb
);
INSERT INTO derivation_state (singleton) VALUES (TRUE) ON CONFLICT DO NOTHING;

CREATE MATERIALIZED VIEW IF NOT EXISTS coverage_hourly
WITH (timescaledb.continuous, timescaledb.materialized_only = false) AS
SELECT time_bucket(INTERVAL '1 hour', polled_at) AS hour,
       line_id, direction, naptan_id, count(DISTINCT vehicle_id) AS vehicles,
       count(*) AS predictions
FROM arrival_predictions GROUP BY 1, 2, 3, 4
WITH NO DATA;
SELECT add_continuous_aggregate_policy('coverage_hourly',
    start_offset => INTERVAL '7 days', end_offset => INTERVAL '1 hour',
    schedule_interval => INTERVAL '5 minutes', if_not_exists => TRUE);

-- Explicit conversion path avoids implicit default columnstore policies.
ALTER TABLE arrival_predictions SET (
    timescaledb.enable_columnstore = true,
    timescaledb.segmentby = 'line_id,direction,naptan_id',
    timescaledb.orderby = 'polled_at DESC'
);
CALL add_columnstore_policy('arrival_predictions', after => INTERVAL '2 hours',
    if_not_exists => TRUE);

-- Conservative pairing: first downstream event, no intervening origin episode,
-- no reuse of a downstream event; missing-vehicle IDs are rejected on ingestion.
CREATE OR REPLACE VIEW get_segments AS
WITH candidates AS (
    SELECT r.route_id, o.vehicle_id, o.line_id, o.direction,
           o.observed_at AS origin_observed_at,
           d.observed_at AS destination_observed_at,
           o.episode_started_at AS origin_episode_started_at,
           d.episode_started_at AS destination_episode_started_at,
           o.method AS origin_method, d.method AS destination_method,
           row_number() OVER (
               PARTITION BY r.route_id, d.vehicle_id, d.episode_started_at
               ORDER BY o.observed_at DESC, o.episode_started_at DESC
           ) AS destination_rank
    FROM route_config r
    JOIN stop_events o ON o.line_id = r.line_id AND o.direction = r.direction
        AND o.naptan_id = r.origin_naptan_id
    JOIN LATERAL (
        SELECT e.* FROM stop_events e
        WHERE e.line_id = r.line_id AND e.direction = r.direction
          AND e.vehicle_id = o.vehicle_id AND e.naptan_id = r.destination_naptan_id
          AND e.observed_at > o.observed_at
          AND e.observed_at <= o.observed_at + INTERVAL '2 hours'
          AND (o.trip_id IS NULL OR e.trip_id IS NULL OR o.trip_id = e.trip_id)
          AND NOT EXISTS (
              SELECT 1 FROM stop_events n
              WHERE n.line_id = o.line_id AND n.direction = o.direction
                AND n.vehicle_id = o.vehicle_id AND n.naptan_id = o.naptan_id
                AND n.observed_at > o.observed_at AND n.observed_at < e.observed_at
          )
        ORDER BY e.observed_at, e.episode_started_at LIMIT 1
    ) d ON TRUE
    WHERE r.active
      -- A vanished long-horizon prediction is not reliable enough for a model trip.
      AND (o.method = 'near_stop_prediction' OR o.last_time_to_station <= 120)
      AND (d.method = 'near_stop_prediction' OR d.last_time_to_station <= 120)
)
SELECT route_id, vehicle_id, origin_observed_at, destination_observed_at,
       line_id, direction, origin_episode_started_at, destination_episode_started_at,
       origin_method, destination_method,
       EXTRACT(EPOCH FROM destination_observed_at - origin_observed_at)::double precision AS ride_seconds
FROM candidates WHERE destination_rank = 1;

-- Trip coverage, deliberately distinct from raw prediction coverage_hourly.
CREATE OR REPLACE VIEW route_coverage AS
SELECT r.route_id, count(s.route_id)::bigint AS trips_observed,
       COALESCE(array_agg(DISTINCT time_bucket(INTERVAL '1 hour', s.origin_observed_at)
           ORDER BY time_bucket(INTERVAL '1 hour', s.origin_observed_at))
           FILTER (WHERE s.route_id IS NOT NULL), ARRAY[]::timestamptz[]) AS hours_covered
FROM route_config r LEFT JOIN get_segments s ON s.route_id = r.route_id
WHERE r.active GROUP BY r.route_id;
